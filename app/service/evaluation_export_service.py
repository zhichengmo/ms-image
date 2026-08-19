"""Export frozen online facts into sanitized Evaluation input Artifacts."""

from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contexts import ControlPlaneContext
from app.core.evaluation import JsonArtifactStore
from app.core.imaging.object_store import ObjectStorageGateway, ObjectStoreError
from app.crud.ai_call import AICallDal
from app.crud.ai_config_record import AIConfigRecordDal
from app.crud.report import ReportDal
from app.crud.stage_checkpoint import StageCheckpointDal
from app.crud.task import TaskDal
from app.schemas.evaluation import EvaluationArtifactInput, EvaluationJobCreate
from app.schemas.evaluation_execution import (
    EvaluationCaseInput,
    EvaluationInputManifest,
)
from app.schemas.evaluation_export import (
    EvaluationCaseExportSpec,
    EvaluationExportJobCreate,
    EvaluationExportJobResponse,
)
from app.service.evaluation_service import (
    EvaluationService,
    EvaluationStateConflictError,
    EvaluationValidationError,
)


class EvaluationExportValidationError(EvaluationValidationError):
    pass


class EvaluationExportStateConflict(EvaluationStateConflictError):
    pass


class EvaluationExportService:
    def __init__(
        self,
        *,
        online_db: AsyncSession,
        evaluation_db: AsyncSession,
        gateway_factory: Callable[[], ObjectStorageGateway],
    ):
        self.online_db = online_db
        self.evaluation_db = evaluation_db
        self.gateway_factory = gateway_factory
        self.task_dal = TaskDal(online_db)
        self.report_dal = ReportDal(online_db)
        self.stage_dal = StageCheckpointDal(online_db)
        self.call_dal = AICallDal(online_db)
        self.config_dal = AIConfigRecordDal(online_db)

    async def export_and_create_job(
        self,
        *,
        payload: EvaluationExportJobCreate,
        context: ControlPlaneContext,
    ) -> EvaluationExportJobResponse:
        if self.online_db.in_transaction() or self.evaluation_db.in_transaction():
            raise EvaluationExportStateConflict(
                "evaluation_export_transaction_already_active"
            )
        async with self.online_db.begin():
            case_rows = [
                await self._build_case_row(spec=spec, payload=payload)
                for spec in payload.cases
            ]
        manifest = EvaluationInputManifest(
            schema_version="evaluation-input.v1",
            cases=case_rows,
        )
        manifest_payload = manifest.model_dump(mode="json")
        manifest_sha256 = self._sha_json(manifest_payload)
        sanitization_payload = {
            "schema_version": "evaluation-sanitization.v1",
            "sanitized": True,
            "policy_version": payload.sanitization_policy_version,
            "exporter_version": "evaluation-export.v1",
            "case_count": len({row.case_id for row in case_rows}),
            "source_manifest_sha256": manifest_sha256,
            "source_identity_sha256": self._sha_json(
                sorted(
                    [
                        {
                            "case_id": row.case_id,
                            "arm_key": row.arm_key,
                            "task_id": row.task_id,
                            "report_id": row.report_id,
                        }
                        for row in case_rows
                    ],
                    key=lambda item: (item["case_id"], item["arm_key"]),
                )
            ),
            "forbidden_field_hits": [],
        }
        requester_scope = hashlib.sha256(
            context.subject_id.encode("utf-8")
        ).hexdigest()[:32]
        request_scope = hashlib.sha256(payload.request_id.encode("utf-8")).hexdigest()[
            :32
        ]
        prefix = f"evaluation/exports/{requester_scope}/{request_scope}"
        try:
            artifact_store = JsonArtifactStore(self.gateway_factory())
            stored_manifest = await artifact_store.store_json(
                object_key=f"{prefix}/input_manifest.json",
                payload=manifest_payload,
            )
            stored_sanitization = await artifact_store.store_json(
                object_key=f"{prefix}/sanitization.json",
                payload=sanitization_payload,
            )
        except ObjectStoreError as exc:
            raise EvaluationExportValidationError(str(exc)) from exc

        split = payload.cases[0].split
        provenance = {
            "sanitized": True,
            "producer": "evaluation_exporter",
            "producer_version": "evaluation-export.v1",
            "sanitization_policy_version": payload.sanitization_policy_version,
            "source_manifest_sha256": manifest_sha256,
        }
        job_payload = EvaluationJobCreate(
            request_id=payload.request_id,
            dataset_fingerprint=payload.dataset_fingerprint,
            gold_fingerprint=payload.gold_fingerprint,
            scorer_fingerprint=payload.scorer_fingerprint,
            experiment_fingerprint=payload.experiment_fingerprint,
            case_split={
                "role": split,
                "case_count": len({item.case_id for item in payload.cases}),
            },
            denominator_contract=payload.denominator_contract,
            input_manifest=EvaluationArtifactInput(
                object_ref=stored_manifest.object_ref,
                content_sha256=stored_manifest.content_sha256,
                provenance={**provenance, "artifact_kind": "input_manifest"},
            ),
            sanitization=EvaluationArtifactInput(
                object_ref=stored_sanitization.object_ref,
                content_sha256=stored_sanitization.content_sha256,
                provenance={**provenance, "artifact_kind": "sanitization"},
            ),
        )
        async with self.evaluation_db.begin():
            job = await EvaluationService(self.evaluation_db).create_job(
                payload=job_payload,
                context=context,
            )
        return EvaluationExportJobResponse(
            job=job,
            input_manifest_sha256=stored_manifest.content_sha256,
            sanitization_sha256=stored_sanitization.content_sha256,
            exported_case_count=len({item.case_id for item in payload.cases}),
        )

    async def _build_case_row(
        self,
        *,
        spec: EvaluationCaseExportSpec,
        payload: EvaluationExportJobCreate,
    ) -> EvaluationCaseInput:
        task = await self.task_dal.get_by_id(spec.task_id)
        if task is None:
            raise EvaluationExportValidationError("evaluation_export_task_not_found")
        report_id = spec.report_id or task.current_report_id
        if not report_id:
            raise EvaluationExportValidationError("evaluation_export_report_missing")
        report = await self.report_dal.get_by_id(report_id)
        if (
            report is None
            or report.task_id != task.id
            or task.current_report_id != report.id
            or report.status not in {"final", "published"}
        ):
            raise EvaluationExportValidationError(
                "evaluation_export_current_report_invalid"
            )
        if (
            task.execution_status != "completed"
            or task.ai_medical_status != report.medical_status
        ):
            raise EvaluationExportValidationError(
                "evaluation_export_task_report_state_invalid"
            )
        stage = await self.stage_dal.get_by_id(report.source_stage_checkpoint_id)
        if (
            stage is None
            or stage.task_id != task.id
            or stage.stage_key != "decision_finalization"
            or stage.status != "completed"
        ):
            raise EvaluationExportValidationError(
                "evaluation_export_finalization_invalid"
            )
        config = await self.config_dal.get_by_id(task.ai_config_id)
        if config is None or config.id != task.ai_config_id:
            raise EvaluationExportValidationError("evaluation_export_config_missing")
        call = None
        if report.source_call_id:
            call = await self.call_dal.get_by_id(report.source_call_id)
            if call is None or call.task_id != task.id:
                raise EvaluationExportValidationError("evaluation_export_call_invalid")
            if call.ai_config_id != config.id:
                raise EvaluationExportValidationError(
                    "evaluation_export_call_config_mismatch"
                )

        manifest_sha256 = (task.request_snapshot_json or {}).get(
            "resolved_manifest_sha256"
        )
        if not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64:
            raise EvaluationExportValidationError(
                "evaluation_export_study_manifest_missing"
            )
        profile_key = config.compiled_pipeline_json.get("profile_key")
        if not isinstance(profile_key, str) or not profile_key:
            raise EvaluationExportValidationError("evaluation_export_profile_missing")
        technical_status, missing_reason = self._technical_status(
            task=task,
            report=report,
            call=call,
        )
        coverage_status = self._coverage_status(
            technical_status=technical_status,
            medical_status=report.medical_status,
        )
        provider_plan = config.provider_plan_json or {}
        connection_ref = provider_plan.get("connection_ref")
        connection = (
            str(connection_ref)[:128]
            if isinstance(connection_ref, str) and connection_ref.strip()
            else (
                "provider-disabled"
                if provider_plan.get("enabled") is False
                else "connection-unavailable"
            )
        )
        source_stage_id = (report.content_json or {}).get("source_stage_id")
        if not isinstance(source_stage_id, str) or not source_stage_id:
            source_stage_id = report.source_stage_checkpoint_id
        route_signal = (report.content_json or {}).get("route_signal")
        if not isinstance(route_signal, str) or not route_signal:
            selected_owner = (report.content_json or {}).get("selected_owner")
            route_signal = (
                "targeted_review"
                if selected_owner == "targeted_review"
                else "primary_final"
            )
        not_applicable_sha = hashlib.sha256(b"not_applicable").hexdigest()
        return EvaluationCaseInput(
            case_id=spec.case_id,
            task_id=task.id,
            report_id=report.id,
            study_revision_id=task.study_revision_id,
            study_manifest_sha256=manifest_sha256,
            expected_status=spec.expected_status,
            predicted_status=report.medical_status,
            technical_status=technical_status,
            coverage_status=coverage_status,
            missing_reason=missing_reason,
            split=spec.split,
            failure_bank_role=spec.failure_bank_role,
            arm_key=spec.arm_key,
            cluster_id=spec.cluster_id,
            dataset_fingerprint=payload.dataset_fingerprint,
            gold_fingerprint=payload.gold_fingerprint,
            scorer_fingerprint=payload.scorer_fingerprint,
            experiment_fingerprint=payload.experiment_fingerprint,
            config_id=config.id,
            config_sha256=(call.config_sha256 if call else self._config_sha(config)),
            profile_key=profile_key,
            profile_sha256=task.compiled_pipeline_sha256,
            prompt_sha256=(call.rendered_prompt_sha256 if call else not_applicable_sha),
            schema_sha256=(call.schema_sha256 if call else not_applicable_sha),
            requested_model=(call.requested_model if call else "not_applicable"),
            actual_model=(call.actual_model if call else None),
            provider=(call.provider_type if call else "not_applicable"),
            connection=connection or "unknown",
            schedule=payload.schedule,
            route_signal=route_signal,
            source_stage_id=source_stage_id,
            source_call_id=(call.id if call else None),
            receipt_status=self._receipt_status(call),
            cost=self._extract_cost(task.budget_consumed_json),
            latency_ms=self._latency_ms(task.started_at, task.finished_at),
        )

    @staticmethod
    def _technical_status(
        *, task: Any, report: Any, call: Any
    ) -> tuple[str, str | None]:
        if report.medical_status in {
            "normal",
            "abnormal",
            "review_required",
            "non_diagnostic",
        }:
            return "completed", None
        error_code = str(
            (getattr(call, "error_code", None) if call else None)
            or task.error_code
            or report.error_code
            or "medical_not_produced"
        )[:200]
        if "budget" in error_code:
            return "over_budget", error_code
        if "partial" in error_code:
            return "partial_sent", error_code
        if "unknown" in error_code:
            return "provider_unknown", error_code
        if "schema" in error_code:
            return "schema_invalid", error_code
        if "missing" in error_code or "not_found" in error_code:
            return "missing", error_code
        return "technical_failure", error_code

    @staticmethod
    def _coverage_status(*, technical_status: str, medical_status: str) -> str:
        if technical_status != "completed":
            return "missing"
        if medical_status in {"review_required", "non_diagnostic"}:
            return "coverage_loss"
        return "complete"

    @staticmethod
    def _receipt_status(call: Any) -> str:
        if call is None or call.provider_type == "disabled":
            return "not_applicable"
        if call.image_receipt_json:
            return (
                "complete"
                if call.image_count_sent == call.image_count_requested
                else "incomplete"
            )
        return "unsupported"

    @staticmethod
    def _extract_cost(value: Any) -> float:
        if not isinstance(value, dict):
            return 0.0
        for key in ("total_cost", "cost", "provider_cost"):
            candidate = value.get(key)
            if isinstance(candidate, (int, float)) and candidate >= 0:
                return round(float(candidate), 8)
        return 0.0

    @staticmethod
    def _latency_ms(started_at: datetime | None, finished_at: datetime | None) -> int:
        if started_at is None or finished_at is None or finished_at < started_at:
            return 0
        return max(0, int((finished_at - started_at).total_seconds() * 1000))

    @staticmethod
    def _config_sha(config: Any) -> str:
        return EvaluationExportService._sha_json(
            {
                "id": config.id,
                "pipeline": config.compiled_pipeline_sha256,
                "provider": config.provider_plan_json,
                "budget": config.budget_policy_json,
            }
        )

    @staticmethod
    def _sha_json(value: Any) -> str:
        return hashlib.sha256(JsonArtifactStore.canonical_json_bytes(value)).hexdigest()


__all__ = [
    "EvaluationExportService",
    "EvaluationExportStateConflict",
    "EvaluationExportValidationError",
]
