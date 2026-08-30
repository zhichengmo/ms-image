import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.ai.config_contract import (
    TASK_REQUEST_SNAPSHOT_V2,
    TASK_REQUEST_SNAPSHOT_V3,
    activation_slot_sha256,
    is_v2_config,
    legacy_activation_slot,
)
from apps.backend.core.ai.clinical_context import freeze_clinical_context
from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    normalize_gateway_profile,
)
from apps.backend.core.ai.prompting.contracts import sha256_json
from apps.backend.core.contexts import CallerContext
from apps.backend.core.config import settings
from apps.backend.core.imaging.manifest import (
    SERIES_IMAGE_MANIFEST_V2,
    ManifestContractError,
    build_series_manifest,
    build_series_manifest_legacy,
    build_study_manifest,
    build_xray_diagnostic_series_manifest,
)
from apps.backend.core.imaging.xray_contract import (
    require_xray_study_image_count,
    requires_xray_runtime_image_contract,
)
from apps.backend.core.pipeline import (
    ZERO_MODEL_PROFILE,
    XRAY_PRIMARY_PROFILE_V2,
    XRAY_TARGETED_REVIEW_PROFILE_V2,
    build_default_registry,
    compile_profile_contract,
)
from apps.backend.crud.ai_config_record import AIConfigRecordDal
from apps.backend.crud.image import ImageDal
from apps.backend.crud.outbox import OutboxDal
from apps.backend.crud.series import SeriesDal
from apps.backend.crud.session import SessionDal
from apps.backend.crud.stage_checkpoint import StageCheckpointDal
from apps.backend.crud.study import StudyDal
from apps.backend.crud.task import TaskDal
from apps.backend.models.imaging_base import new_opaque_id
from apps.backend.schemas.task import (
    TaskCreate,
    TaskClinicalContext,
    TaskPageQuery,
    TaskPageResult,
    TaskResponse,
    TaskStatusResponse,
)


class TaskServiceError(ValueError):
    pass


class TaskNotFoundError(TaskServiceError):
    pass


class TaskAccessDeniedError(TaskServiceError):
    pass


class TaskStateConflictError(TaskServiceError):
    pass


class TaskIdempotencyConflictError(TaskServiceError):
    pass


class TaskService:
    ZERO_MODEL_CONFIG_KEY = "zero_model_replay"
    DIAGNOSE_CONFIG_KEYS = {
        "cat": "xray_diagnose_cat",
        "dog": "xray_diagnose_dog",
    }
    DIAGNOSE_PROMPT_KEYS = {
        "cat": "xray_cat_primary",
        "dog": "xray_dog_primary",
    }
    TERMINAL_EXECUTION_STATUSES = TaskDal.TERMINAL_EXECUTION_STATUSES
    TASK_CONFIG_KEYS = {
        "replay": ZERO_MODEL_CONFIG_KEY,
    }
    TASK_PROFILES = {
        "replay": frozenset({ZERO_MODEL_PROFILE}),
        "diagnose": frozenset(
            {XRAY_PRIMARY_PROFILE_V2, XRAY_TARGETED_REVIEW_PROFILE_V2}
        ),
    }

    def __init__(self, db: AsyncSession):
        self.session_dal = SessionDal(db)
        self.study_dal = StudyDal(db)
        self.series_dal = SeriesDal(db)
        self.config_dal = AIConfigRecordDal(db)
        self.image_dal = ImageDal(db)
        self.task_dal = TaskDal(db)
        self.stage_dal = StageCheckpointDal(db)
        self.outbox_dal = OutboxDal(db)
        self.registry = build_default_registry()

    @staticmethod
    def _response(task) -> TaskResponse:
        return TaskResponse.model_validate(task)

    async def create_task(
        self, *, payload: TaskCreate, caller: CallerContext
    ) -> TaskResponse:
        config_key = self._config_key_for_task(
            task_type=payload.task_type,
            species=payload.species,
        )
        allowed_profiles = self.TASK_PROFILES.get(payload.task_type)
        if config_key is None or allowed_profiles is None:
            raise TaskStateConflictError("task_type_not_supported")
        study = await self.study_dal.get_by_id(payload.study_id)
        if study is None:
            raise TaskNotFoundError("study_not_found")
        session = await self.session_dal.get_by_id_for_update(study.session_id)
        if session is None:
            raise TaskNotFoundError("session_not_found")
        if session.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        business_key = self._sha(
            {
                "requester_id": caller.subject_id,
                "request_id": payload.request_id,
                "task_type": payload.task_type,
            }
        )
        existing = await self.task_dal.get_by_business_key(business_key)
        if session.status not in {"open", "processing"} and existing is None:
            raise TaskStateConflictError("session_not_accepting_tasks")
        if (
            study.status != "ready"
            or study.revision_id != payload.study_revision_id
            or not study.resolved_manifest_sha256
        ):
            raise TaskStateConflictError("study_revision_not_ready")
        config = await self._get_active_config(
            config_key=config_key,
            modality_type=study.modality_type,
            task_type=payload.task_type,
        )
        if config is None:
            raise TaskStateConflictError("task_config_not_active")
        self._validate_species_config_binding(
            config=config,
            task_type=payload.task_type,
            species=payload.species,
        )
        profile_key, contract, profile_sha = self._validate_assignable_config(
            config=config,
            allowed_profiles=allowed_profiles,
        )
        first_definition = contract["stages"][0]

        series = await self.series_dal.list_for_study(study.id)
        xray_image_contract_required = requires_xray_runtime_image_contract(
            modality_type=study.modality_type,
            task_type=payload.task_type,
            profile_key=profile_key,
        )
        ready_images = (
            await self.image_dal.list_ready_diagnostic_for_series_ids(
                [item.id for item in series]
            )
            if xray_image_contract_required
            else await self.image_dal.list_ready_for_series_ids(
                [item.id for item in series]
            )
        )
        self._require_xray_task_image_count(
            modality_type=study.modality_type,
            task_type=payload.task_type,
            profile_key=profile_key,
            image_count=len(ready_images),
        )
        run_mode = "replay" if payload.task_type == "replay" else "validation_only"
        report_required = payload.task_type == "diagnose"
        snapshot = self._build_request_snapshot(
            study=study,
            series=series,
            config=config,
            profile_key=profile_key,
            compiled_profile=contract,
            task_type=payload.task_type,
            species=payload.species,
            clinical_context=payload.clinical_context,
            series_images=ready_images,
        )
        request_sha = self._sha(snapshot)
        if existing is not None:
            self._ensure_idempotent_task(
                task=existing,
                study_id=study.id,
                study_revision_id=study.revision_id,
                config_id=config.id,
                request_sha=request_sha,
            )
            return self._response(existing)

        task_id = new_opaque_id()
        stage_id = new_opaque_id()
        stage_input = {
            "task_id": task_id,
            "study_revision_id": study.revision_id,
            "manifest_sha256": study.resolved_manifest_sha256,
        }
        stage_input_sha = self._sha(stage_input)
        assignment_sha = self._sha(
            {
                "config_id": config.id,
                "config_sha256": config.config_sha256,
                "release_fingerprint": config.release_fingerprint,
                "profile": profile_sha,
                "task_type": payload.task_type,
                "run_mode": run_mode,
            }
        )
        task_values = {
            "id": task_id,
            "study_id": study.id,
            "requester_id": caller.subject_id,
            "request_id": payload.request_id,
            "task_type": payload.task_type,
            "business_key": business_key,
            "contract_version": "task.v1",
            "ai_config_id": config.id,
            "compiled_pipeline_sha256": profile_sha,
            "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "routing_policy_version": "control-plane.v1",
            "assignment_sha256": assignment_sha,
            "study_revision_id": study.revision_id,
            "report_required": report_required,
            "run_mode": run_mode,
            "experiment_arm_id": None,
            "execution_status": "queued",
            "ai_medical_status": "not_produced",
            "state_version": 0,
            "request_snapshot_json": snapshot,
            "request_sha256": request_sha,
            "budget_snapshot_json": config.budget_policy_json,
            "budget_reserved_json": {
                "contract_version": "task-budget-reservation.v1",
                "budget_policy_sha256": self._sha(config.budget_policy_json),
                "reserved_call_units": 0,
                "reserved_attempts": 0,
            },
            "budget_consumed_json": {},
            "current_report_id": None,
            "attempt_no": 1,
            "trace_id": payload.trace_id,
        }
        task = await self.task_dal.create_idempotent(task_values)
        if task is None:
            existing = await self.task_dal.get_by_business_key(business_key)
            if existing is None:
                raise TaskIdempotencyConflictError("task_create_conflict")
            self._ensure_idempotent_task(
                task=existing,
                study_id=study.id,
                study_revision_id=study.revision_id,
                config_id=config.id,
                request_sha=request_sha,
            )
            return self._response(existing)
        stage = await self.stage_dal.create_idempotent(
            {
                "id": stage_id,
                "task_id": task.id,
                "task_attempt_no": 1,
                "stage_instance_key": f"{first_definition['stage_key']}:1",
                "stage_no": 1,
                "stage_key": first_definition["stage_key"],
                "handler_key": first_definition["handler_key"],
                "handler_version": first_definition["handler_version"],
                "status": "queued",
                "state_version": 0,
                "lease_generation": 0,
                "input_json": stage_input,
                "input_sha256": stage_input_sha,
                "retry_count": 0,
            }
        )
        if stage is None:
            raise TaskStateConflictError("first_stage_create_conflict")
        message = {
            "task_id": task.id,
            "stage_checkpoint_id": stage.id,
            "expected_state_version": stage.state_version,
            "trace_id": payload.trace_id,
        }
        event = await self.outbox_dal.create_idempotent(
            {
                "id": new_opaque_id(),
                "aggregate_type": "stage",
                "aggregate_id": stage.id,
                "aggregate_version": stage.state_version,
                "event_key": f"stage:{stage.id}:execute:{stage.state_version}",
                "event_type": "execute_stage",
                "destination_key": OutboxDal.STAGE_DESTINATION_KEY,
                "trace_id": payload.trace_id,
                "message_version": OutboxDal.STAGE_MESSAGE_VERSION,
                "message_json": message,
                "message_sha256": OutboxDal.message_sha256(message),
                "publish_status": "pending",
                "publish_attempt_count": 0,
            }
        )
        if event is None:
            raise TaskStateConflictError("first_stage_event_conflict")
        return self._response(task)

    @staticmethod
    def _require_xray_task_image_count(
        *,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        image_count: int,
    ) -> None:
        if not requires_xray_runtime_image_contract(
            modality_type=modality_type,
            task_type=task_type,
            profile_key=profile_key,
        ):
            return
        try:
            require_xray_study_image_count(image_count)
        except ValueError as exc:
            raise TaskStateConflictError(
                "xray_task_image_count_out_of_range"
            ) from exc

    @classmethod
    def _config_key_for_task(
        cls,
        *,
        task_type: str,
        species: str | None,
    ) -> str | None:
        if task_type == "diagnose":
            config_key = cls.DIAGNOSE_CONFIG_KEYS.get(species or "")
            if config_key is None:
                raise TaskStateConflictError("task_species_snapshot_invalid")
            return config_key
        return cls.TASK_CONFIG_KEYS.get(task_type)

    @classmethod
    def _validate_species_config_binding(
        cls,
        *,
        config,
        task_type: str,
        species: str | None,
    ) -> None:
        if task_type != "diagnose":
            return
        expected_config_key = cls.DIAGNOSE_CONFIG_KEYS.get(species or "")
        expected_prompt_key = cls.DIAGNOSE_PROMPT_KEYS.get(species or "")
        if (
            expected_config_key is None
            or expected_prompt_key is None
            or config.config_key != expected_config_key
            or config.prompt_key != expected_prompt_key
            or config.profile_key
            not in {XRAY_PRIMARY_PROFILE_V2, XRAY_TARGETED_REVIEW_PROFILE_V2}
        ):
            raise TaskStateConflictError("task_config_invalid")

    async def _get_active_config(
        self,
        *,
        config_key: str,
        modality_type: str,
        task_type: str,
    ):
        """Resolve the v2 active slot first and retain v1 read compatibility."""
        experiment_scope_key = settings.XRAY_TARGETED_EXPERIMENT_SCOPE_KEY.strip()
        if task_type == "diagnose" and experiment_scope_key:
            return await self.config_dal.get_active(
                activation_slot_sha256(
                    config_key=config_key,
                    modality_type=modality_type,
                    task_type=task_type,
                    activation_scope="experiment",
                    scope_key=experiment_scope_key,
                )
            )
        v2_slot = activation_slot_sha256(
            config_key=config_key,
            modality_type=modality_type,
            task_type=task_type,
            activation_scope="global",
            scope_key="global",
        )
        config = await self.config_dal.get_active(v2_slot)
        if config is not None:
            return config
        return await self.config_dal.get_active(
            legacy_activation_slot(
                config_key=config_key,
                modality_type=modality_type,
                task_type=task_type,
                activation_scope="global",
                scope_key="global",
            )
        )

    def _validate_assignable_config(
        self,
        *,
        config,
        allowed_profiles: frozenset[str],
    ) -> tuple[str, dict, str]:
        """Validate only the active Config facts required before Task freezing."""
        capability_manifest = config.capability_manifest_json
        if config.status != "active" or not isinstance(capability_manifest, dict):
            raise TaskStateConflictError("task_config_invalid")

        if is_v2_config(config):
            try:
                gateway_profile = normalize_gateway_profile(config.gateway_profile_json)
            except GatewayContractError as exc:
                raise TaskStateConflictError(str(exc)) from exc
            if capability_manifest.get("provider_disabled") is not (
                not gateway_profile["provider_enabled"]
            ) or capability_manifest.get("gateway_profile_sha256") != sha256_json(
                gateway_profile
            ):
                raise TaskStateConflictError("task_config_gateway_profile_mismatch")
            profile_key = config.profile_key
            required_snapshot_fields = (
                config.config_sha256,
                config.release_fingerprint,
                config.prompt_content_sha256,
                config.model_snapshot_sha256,
                config.output_schema_sha256,
                config.compiled_pipeline_sha256,
                config.stage_registry_contract_version,
            )
            if (
                not isinstance(profile_key, str)
                or not profile_key
                or any(
                    not isinstance(value, str) or not value
                    for value in required_snapshot_fields
                )
            ):
                raise TaskStateConflictError("task_config_v2_snapshot_invalid")
        else:
            provider_plan = config.provider_plan_json
            if (
                capability_manifest.get("provider_disabled") is not True
                or not isinstance(provider_plan, dict)
                or provider_plan.get("enabled") is not False
            ):
                raise TaskStateConflictError("task_config_invalid")
            pipeline = config.compiled_pipeline_json
            profile_key = (
                pipeline.get("profile_key") if isinstance(pipeline, dict) else None
            )

        if profile_key not in allowed_profiles:
            raise TaskStateConflictError("task_profile_not_allowed")
        if (
            not isinstance(config.compiled_pipeline_json, dict)
            or config.compiled_pipeline_json.get("profile_key") != profile_key
        ):
            raise TaskStateConflictError("task_config_pipeline_invalid")
        contract, profile_sha = compile_profile_contract(profile_key, self.registry)
        if (
            profile_sha != config.compiled_pipeline_sha256
            or config.stage_registry_contract_version != self.registry.CONTRACT_VERSION
        ):
            raise TaskStateConflictError("config_profile_fingerprint_conflict")
        if not contract.get("stages"):
            raise TaskStateConflictError("compiled_profile_empty")
        if contract["stages"][0].get("stage_key") != "study_preparation":
            raise TaskStateConflictError("compiled_profile_entry_invalid")
        return profile_key, contract, profile_sha

    @staticmethod
    def _build_request_snapshot(
        *,
        study,
        series,
        config,
        profile_key: str,
        compiled_profile: dict,
        task_type: str,
        species: str | None,
        clinical_context: TaskClinicalContext | None = None,
        series_images: list | None = None,
    ) -> dict:
        """Freeze the active Config identity once, without dereferencing sources later."""
        is_config_v2 = is_v2_config(config)
        if task_type == "diagnose" and species not in {"cat", "dog"}:
            # Species is a caller-bounded fact for every new diagnostic Task.
            # Reject it before durable Task/Stage/Outbox creation instead of
            # persisting a v2 snapshot the XRay Prompt command would reject.
            raise TaskStateConflictError("task_species_snapshot_invalid")
        if task_type != "diagnose" and clinical_context is not None:
            raise TaskStateConflictError("task_clinical_context_diagnose_only")
        frozen_clinical_context = freeze_clinical_context(
            clinical_context.model_dump(mode="json")
            if clinical_context is not None
            else None
        )

        legacy_series_snapshot = [
            {
                "series_id": item.id,
                "manifest_sha256": item.manifest_sha256,
                "actual_image_count": item.actual_image_count,
            }
            for item in series
        ]
        snapshot = {
            "study_id": study.id,
            "study_revision_id": study.revision_id,
            "resolved_manifest_sha256": study.resolved_manifest_sha256,
            # Replay preserves its legacy compatibility value. Diagnose has
            # already been fail-closed above, regardless of Config generation.
            "species": species if task_type == "diagnose" else species or "unknown",
            "series": legacy_series_snapshot,
            "ai_config_id": config.id,
            "config_key": config.config_key,
            "config_version": config.version,
            "config_sha256": config.config_sha256,
            "release_fingerprint": config.release_fingerprint,
            "profile_key": profile_key,
            "compiled_profile": compiled_profile,
            **frozen_clinical_context.snapshot_fields(),
        }
        if is_config_v2:
            snapshot_contract_version = TASK_REQUEST_SNAPSHOT_V3
            if series_images is not None:
                try:
                    study_manifest = build_study_manifest(series)
                    if study_manifest.sha256 != study.resolved_manifest_sha256:
                        raise TaskStateConflictError(
                            "task_study_manifest_snapshot_mismatch"
                        )
                    images_by_series: dict[str, list] = {
                        item["series_id"]: [] for item in study_manifest.items
                    }
                    for image in series_images:
                        if image.series_id not in images_by_series:
                            raise TaskStateConflictError(
                                "task_series_image_scope_mismatch"
                            )
                        images_by_series[image.series_id].append(image)
                    rows_by_id = {item.id: item for item in series}
                    frozen_series: list[dict] = []
                    manifest_contracts: set[str] = set()
                    for study_item in study_manifest.items:
                        series_id = study_item["series_id"]
                        row = rows_by_id[series_id]
                        ready_images = images_by_series[series_id]
                        image_manifest = (
                            build_xray_diagnostic_series_manifest(ready_images)
                            if requires_xray_runtime_image_contract(
                                modality_type=getattr(
                                    study, "modality_type", None
                                ),
                                task_type=task_type,
                                profile_key=profile_key,
                            )
                            else build_series_manifest(ready_images)
                        )
                        legacy_manifest = build_series_manifest_legacy(ready_images)
                        if len(image_manifest.items) != row.actual_image_count:
                            raise TaskStateConflictError(
                                "task_series_manifest_snapshot_mismatch"
                            )
                        d1_match = image_manifest.sha256 == row.manifest_sha256
                        legacy_match = legacy_manifest.sha256 == row.manifest_sha256
                        if not d1_match and not legacy_match:
                            raise TaskStateConflictError(
                                "task_series_manifest_snapshot_mismatch"
                            )
                        if d1_match != legacy_match:
                            manifest_contracts.add("d1" if d1_match else "legacy")
                        frozen_series.append(
                            {
                                "series_id": series_id,
                                "series_key": study_item["series_key"],
                                "series_no": study_item["series_no"],
                                "manifest_contract_version": (SERIES_IMAGE_MANIFEST_V2),
                                "manifest_sha256": image_manifest.sha256,
                                "actual_image_count": len(image_manifest.items),
                                "ordered_images": image_manifest.as_list(),
                            }
                        )
                    if len(manifest_contracts) > 1:
                        raise TaskStateConflictError(
                            "task_series_manifest_snapshot_mismatch"
                        )
                    if manifest_contracts == {"legacy"}:
                        snapshot_contract_version = TASK_REQUEST_SNAPSHOT_V2
                    else:
                        snapshot["series"] = frozen_series
                except ManifestContractError as exc:
                    raise TaskStateConflictError(str(exc)) from exc
            if (
                profile_key
                in {XRAY_PRIMARY_PROFILE_V2, XRAY_TARGETED_REVIEW_PROFILE_V2}
                and snapshot_contract_version != TASK_REQUEST_SNAPSHOT_V3
            ):
                raise TaskStateConflictError(
                    "task_result_contract_requires_snapshot_v3"
                )
            snapshot.update(
                {
                    "snapshot_contract_version": snapshot_contract_version,
                    "config_contract_version": config.config_contract_version,
                    "prompt_content_sha256": config.prompt_content_sha256,
                    "model_snapshot_sha256": config.model_snapshot_sha256,
                    "output_schema_sha256": config.output_schema_sha256,
                    "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
                    "stage_registry_contract_version": (
                        config.stage_registry_contract_version
                    ),
                }
            )
            return snapshot

        prompt_bundle = config.prompt_bundle_json
        schema_bundle = config.schema_bundle_json
        if not isinstance(prompt_bundle, dict) or not isinstance(schema_bundle, dict):
            raise TaskStateConflictError("task_config_v1_bundle_invalid")
        prompt_bundle_sha = prompt_bundle.get("bundle_sha256")
        schema_bundle_sha = schema_bundle.get("bundle_sha256")
        if not isinstance(prompt_bundle_sha, str) or not isinstance(
            schema_bundle_sha, str
        ):
            raise TaskStateConflictError("task_config_v1_bundle_invalid")
        snapshot.update(
            {
                "prompt_bundle_sha256": prompt_bundle_sha,
                "schema_bundle_sha256": schema_bundle_sha,
            }
        )
        return snapshot

    @staticmethod
    def _ensure_idempotent_task(
        *, task, study_id: str, study_revision_id: str, config_id: str, request_sha: str
    ) -> None:
        if (
            task.study_id != study_id
            or task.study_revision_id != study_revision_id
            or task.ai_config_id != config_id
            or task.request_sha256 != request_sha
        ):
            raise TaskIdempotencyConflictError("task_idempotency_conflict")

    async def get_task(self, *, task_id: str, caller: CallerContext) -> TaskResponse:
        task = await self.task_dal.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError("task_not_found")
        if task.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        return self._response(task)

    async def page_tasks(
        self, *, query: TaskPageQuery, caller: CallerContext
    ) -> TaskPageResult:
        study = None
        study_session = None
        if query.study_id is not None:
            study = await self.study_dal.get_by_id(query.study_id)
            if study is None:
                raise TaskNotFoundError("study_not_found")
            study_session = await self.session_dal.get_by_id(study.session_id)
            if study_session is None:
                raise TaskNotFoundError("session_not_found")
            if study_session.requester_id != caller.subject_id:
                raise TaskAccessDeniedError("task_access_denied")

        if query.session_id is not None:
            session = (
                study_session
                if study_session is not None and study_session.id == query.session_id
                else await self.session_dal.get_by_id(query.session_id)
            )
            if session is None:
                raise TaskNotFoundError("session_not_found")
            if session.requester_id != caller.subject_id:
                raise TaskAccessDeniedError("task_access_denied")
            if study is not None and study.session_id != session.id:
                raise TaskStateConflictError("task_query_scope_mismatch")

        rows, total = await self.task_dal.page_for_owner(
            requester_id=caller.subject_id,
            session_id=query.session_id,
            study_id=query.study_id,
            execution_status=query.execution_status,
            task_type=query.task_type,
            created_from=query.created_from,
            created_to=query.created_to,
            page=query.page,
            limit=query.page_size,
        )
        return TaskPageResult(
            data=[TaskStatusResponse.model_validate(item) for item in rows],
            total=total,
            page=query.page,
            limit=query.page_size,
        )

    async def has_non_terminal_tasks_for_session(self, *, session_id: str) -> bool:
        tasks = await self.task_dal.list_non_terminal_for_session(session_id=session_id)
        return bool(tasks)

    async def request_cancellation_for_session(
        self, *, session_id: str, requester_id: str, reason: str
    ) -> int:
        tasks = await self.task_dal.list_non_terminal_for_session(
            session_id=session_id,
            for_update=True,
        )
        for task in tasks:
            if task.requester_id != requester_id:
                raise TaskStateConflictError("session_task_owner_conflict")
            await self._request_cancel_locked_task(
                task=task,
                requested_by_id=requester_id,
                reason=reason,
            )
        return len(tasks)

    async def cancel_task(
        self,
        *,
        task_id: str,
        expected_version: int,
        reason: str | None,
        caller: CallerContext,
    ) -> TaskResponse:
        task = await self.task_dal.get_by_id_for_update(task_id)
        if task is None:
            raise TaskNotFoundError("task_not_found")
        if task.requester_id != caller.subject_id:
            raise TaskAccessDeniedError("task_access_denied")
        if task.cancel_requested_at is not None:
            return self._response(task)
        if (
            task.execution_status in self.TERMINAL_EXECUTION_STATUSES
            or task.state_version != expected_version
        ):
            raise TaskStateConflictError("task_cancel_conflict")
        updated = await self._request_cancel_locked_task(
            task=task,
            requested_by_id=caller.subject_id,
            reason=reason,
        )
        return self._response(updated)

    async def _request_cancel_locked_task(
        self,
        *,
        task,
        requested_by_id: str,
        reason: str | None,
    ):
        if task.cancel_requested_at is not None:
            return task
        if task.execution_status in self.TERMINAL_EXECUTION_STATUSES:
            raise TaskStateConflictError("task_cancel_conflict")
        normalized_reason = (reason or "").strip() or "caller_cancelled"
        updated = await self.task_dal.cas_update(
            task_id=task.id,
            expected_version=task.state_version,
            values={
                "cancel_requested_by_id": requested_by_id,
                "cancel_reason": normalized_reason[:200],
                "cancel_requested_at": datetime.utcnow(),
            },
        )
        if updated is None:
            raise TaskStateConflictError("task_cancel_conflict")
        return updated

    @staticmethod
    def _sha(value: dict) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
