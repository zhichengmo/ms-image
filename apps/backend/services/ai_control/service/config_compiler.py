"""Immutable ``ai-config.v2`` compiler.

The compiler has no I/O other than loading the versioned output-schema asset from
this repository.  Source rows are supplied by ``AIConfigService`` after it has
obtained them exclusively through entity DALs.  That keeps the compiler
reproducible and prevents an accidental Runtime read of current Prompt, Pool or
Connection records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from apps.backend.core.ai.config_contract import AI_CONFIG_V2
from apps.backend.core.ai.anatomy_localization_contract import (
    ANATOMY_LABEL_CONTRACT_V1,
    ANATOMY_LOCALIZATION_CONTRACT_V1,
    AnatomyLocalizationContractError,
    anatomy_label_contract_sha256,
)
from apps.backend.core.ai.gateway.contracts import (
    GatewayContractError,
    normalize_gateway_profile,
)
from apps.backend.core.ai.image_quality_contract import (
    XRAY_IMAGE_QUALITY_CONTRACT_V1,
)
from apps.backend.core.ai.study_screening_contract import (
    XRAY_STUDY_SCREENING_CONTRACT_V1,
    XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
)
from apps.backend.core.ai.system_analysis_contract import (
    XRAY_SYSTEM_ANALYSIS_CONTRACT_V1,
)
from apps.backend.core.ai.report_generation_contract import (
    XRAY_FINAL_REPORT_CONTRACT_V1,
)
from apps.backend.core.ai.connection_contract import (
    ConnectionContractError,
    canonical_connection_metadata_sha256,
    canonicalize_connection_base_url,
)
from apps.backend.core.ai.prompting.contracts import sha256_json, sha256_text
from apps.backend.core.ai.prompting.message_contract import (
    PromptMessageContractError,
    validate_prompt_message_template,
)
from apps.backend.core.ai.prompting.renderer import (
    PromptRenderError,
    PromptRenderer,
)
from apps.backend.core.ai.xray_result_contract import COMPLETE_MEDICAL_RESULT_V2
from apps.backend.core.imaging.xray_contract import (
    XRAY_ANATOMY_LOCALIZATION_TASK_TYPE,
    XRAY_IMAGE_QUALITY_TASK_TYPE,
    XRAY_STUDY_SCREENING_TASK_TYPE,
    XRAY_SYSTEM_ANALYSIS_TASK_TYPE,
    XRAY_STUDY_MAX_IMAGE_COUNT,
    requires_exact_xray_five_image_config_contract,
)
from apps.backend.core.pipeline import (
    PipelineContractError,
    StageRegistry,
    ZERO_MODEL_PROFILE,
    XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
    XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1,
    XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
    XRAY_IMAGE_QUALITY_PROFILE_V1,
    XRAY_PRIMARY_PROFILE_V2,
    XRAY_REPORT_GENERATION_PROFILE_V1,
    XRAY_STUDY_SCREENING_PROFILE_V1,
    XRAY_STUDY_SCREENING_PROFILE_V2,
    XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
    XRAY_TARGETED_REVIEW_PROFILE_V2,
    compile_profile_contract,
)
from apps.backend.models.ai_api_connection import AIAPIConnection
from apps.backend.models.ai_model_pool import AIModelPool
from apps.backend.models.ai_prompt_template import AIPromptTemplate
from apps.backend.schemas.ai_control import (
    BudgetPolicyContract,
    ModelPoolLanePlanContract,
)
from apps.backend.services.ai_control.service.errors import AIControlValidationError

_OUTPUT_SCHEMA_V1_RELATIVE_PATH = Path(
    "prompts/xray/complete_medical_result.schema.json"
)
_OUTPUT_SCHEMA_V2_RELATIVE_PATH = Path(
    "prompts/xray/complete_medical_result.v2.schema.json"
)
_OUTPUT_SCHEMA_ANATOMY_LOCALIZATION_V1_RELATIVE_PATH = Path(
    "prompts/xray/anatomy_localization.v1.schema.json"
)
_OUTPUT_SCHEMA_IMAGE_QUALITY_V1_RELATIVE_PATH = Path(
    "prompts/xray/image_quality.v1.schema.json"
)
_OUTPUT_SCHEMA_STUDY_SCREENING_V1_RELATIVE_PATH = Path(
    "prompts/xray/study_screening.v1.schema.json"
)
_OUTPUT_SCHEMA_STUDY_SCREENING_V2_RELATIVE_PATH = Path(
    "prompts/xray/study_screening.v2.schema.json"
)
_OUTPUT_SCHEMA_SYSTEM_ANALYSIS_V1_RELATIVE_PATH = Path(
    "prompts/xray/system_analysis.v1.schema.json"
)
_OUTPUT_SCHEMA_REPORT_GENERATION_V1_RELATIVE_PATH = Path(
    "prompts/xray/final_report.v1.schema.json"
)
_OUTPUT_SCHEMA_V1_CONTRACT_VERSION = "complete-medical-result.v1"
_V1_RESULT_PROFILES = frozenset(
    {ZERO_MODEL_PROFILE, "xray_primary_v1", "xray_targeted_review_v1"}
)
_V2_RESULT_PROFILES = frozenset(
    {
        XRAY_PRIMARY_PROFILE_V2,
        XRAY_TARGETED_REVIEW_PROFILE_V2,
        XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1,
        XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
    }
)
_ANATOMY_LOCALIZATION_PROMPT_BINDINGS = {
    "xray_anatomy_localization_cat": "xray_cat_anatomy_localization",
    "xray_anatomy_localization_dog": "xray_dog_anatomy_localization",
}
_IMAGE_QUALITY_PROMPT_BINDINGS = {
    "xray_image_quality_cat": "xray_cat_image_quality",
    "xray_image_quality_dog": "xray_dog_image_quality",
}
_STUDY_SCREENING_PROMPT_BINDINGS = {
    "xray_study_screening_cat": "xray_cat_study_screening",
    "xray_study_screening_dog": "xray_dog_study_screening",
}
_SYSTEM_ANALYSIS_PROMPT_BINDINGS = {
    "xray_system_analysis_cat": "xray_cat_system_analysis",
    "xray_system_analysis_dog": "xray_dog_system_analysis",
}
_TARGETED_REVIEW_PROMPT_BINDINGS = {
    "xray_targeted_review_cat": "xray_cat_targeted_review",
    "xray_targeted_review_dog": "xray_dog_targeted_review",
}
_REPORT_GENERATION_PROMPT_BINDINGS = {
    "xray_report_generation_cat": "xray_cat_report_generation",
    "xray_report_generation_dog": "xray_dog_report_generation",
}
_FULL_CHAIN_PRIMARY_PROMPT_BINDINGS = {
    "xray_diagnose_cat": "xray_cat_primary_adjudication",
    "xray_diagnose_dog": "xray_dog_primary_adjudication",
}


@dataclass(frozen=True)
class CompiledAIConfig:
    """All immutable v2 facts, including internal-only runtime snapshots."""

    values: dict[str, Any]
    capability_manifest_sha256: str
    budget_policy_sha256: str

    def preview(self) -> dict[str, str]:
        values = self.values
        return {
            "config_contract_version": values["config_contract_version"],
            "config_key": values["config_key"],
            "version": values["version"],
            "profile_key": values["profile_key"],
            "prompt_template_id": values["prompt_template_id"],
            "prompt_key": values["prompt_key"],
            "prompt_version": values["prompt_version"],
            "prompt_content_sha256": values["prompt_content_sha256"],
            "model_pool_id": values["model_pool_id"],
            "model_pool_key": values["model_pool_key"],
            "model_pool_version": values["model_pool_version"],
            "model_snapshot_sha256": values["model_snapshot_sha256"],
            "output_schema_sha256": values["output_schema_sha256"],
            "compiled_pipeline_sha256": values["compiled_pipeline_sha256"],
            "stage_registry_contract_version": values[
                "stage_registry_contract_version"
            ],
            "capability_manifest_sha256": self.capability_manifest_sha256,
            "budget_policy_sha256": self.budget_policy_sha256,
            "config_sha256": values["config_sha256"],
            "release_fingerprint": values["release_fingerprint"],
        }


class AIConfigCompiler:
    """Compile and deterministically re-verify a v2 Config snapshot."""

    def __init__(self, registry: StageRegistry):
        self.registry = registry

    @staticmethod
    def _output_schema(*, profile_key: str) -> dict[str, Any]:
        if profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1:
            relative_path = _OUTPUT_SCHEMA_ANATOMY_LOCALIZATION_V1_RELATIVE_PATH
            contract_version = ANATOMY_LOCALIZATION_CONTRACT_V1
        elif profile_key == XRAY_IMAGE_QUALITY_PROFILE_V1:
            relative_path = _OUTPUT_SCHEMA_IMAGE_QUALITY_V1_RELATIVE_PATH
            contract_version = XRAY_IMAGE_QUALITY_CONTRACT_V1
        elif profile_key == XRAY_STUDY_SCREENING_PROFILE_V1:
            relative_path = _OUTPUT_SCHEMA_STUDY_SCREENING_V1_RELATIVE_PATH
            contract_version = XRAY_STUDY_SCREENING_CONTRACT_V1
        elif profile_key == XRAY_STUDY_SCREENING_PROFILE_V2:
            relative_path = _OUTPUT_SCHEMA_STUDY_SCREENING_V2_RELATIVE_PATH
            contract_version = XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2
        elif profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1:
            relative_path = _OUTPUT_SCHEMA_SYSTEM_ANALYSIS_V1_RELATIVE_PATH
            contract_version = XRAY_SYSTEM_ANALYSIS_CONTRACT_V1
        elif profile_key == XRAY_REPORT_GENERATION_PROFILE_V1:
            relative_path = _OUTPUT_SCHEMA_REPORT_GENERATION_V1_RELATIVE_PATH
            contract_version = XRAY_FINAL_REPORT_CONTRACT_V1
        elif profile_key in _V2_RESULT_PROFILES:
            relative_path = _OUTPUT_SCHEMA_V2_RELATIVE_PATH
            contract_version = COMPLETE_MEDICAL_RESULT_V2
        elif profile_key in _V1_RESULT_PROFILES:
            relative_path = _OUTPUT_SCHEMA_V1_RELATIVE_PATH
            contract_version = _OUTPUT_SCHEMA_V1_CONTRACT_VERSION
        else:
            raise AIControlValidationError("output_schema_profile_unsupported")
        root = Path(__file__).resolve().parents[5]
        path = root / relative_path
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIControlValidationError("output_schema_asset_unavailable") from exc
        if not isinstance(loaded, dict):
            raise AIControlValidationError("output_schema_asset_invalid")
        # The code-owned schema has an explicit stable business version without
        # exposing the old Prompt Catalog / Schema Bundle abstraction.
        if loaded.get("x-ms-image-contract-version") not in (
            None,
            contract_version,
        ):
            raise AIControlValidationError("output_schema_contract_version_conflict")
        result = dict(loaded)
        result["x-ms-image-contract-version"] = contract_version
        if profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1:
            try:
                label_sha256 = anatomy_label_contract_sha256()
            except AnatomyLocalizationContractError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if (
                result.get("x-ms-image-label-contract-version")
                != ANATOMY_LABEL_CONTRACT_V1
                or result.get("x-ms-image-label-contract-sha256")
                != label_sha256
            ):
                raise AIControlValidationError(
                    "anatomy_localization_schema_label_contract_mismatch"
                )
        return result

    @staticmethod
    def _validate_prompt(
        prompt: AIPromptTemplate, *, require_validated: bool
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        if prompt.language != "zh-CN":
            raise AIControlValidationError("config_prompt_language_invalid")
        if require_validated and prompt.status != "validated":
            raise AIControlValidationError("config_prompt_validated_required")
        if not require_validated and prompt.status not in {"validated", "retired"}:
            raise AIControlValidationError("config_prompt_history_state_invalid")
        try:
            content = PromptRenderer.validate_template(
                content=prompt.content,
                variables_json=prompt.variables_json,
            )
            message_contract = validate_prompt_message_template(
                content=content,
                message_contract_json=prompt.message_contract_json,
            )
        except (PromptRenderError, PromptMessageContractError) as exc:
            raise AIControlValidationError(str(exc)) from exc
        AIConfigCompiler._validate_prompt_message_contract_variables(
            variables_json=prompt.variables_json,
            message_contract=message_contract,
        )
        if not content.strip():
            raise AIControlValidationError("prompt_content_empty")
        content_sha256 = sha256_text(content)
        if content_sha256 != prompt.content_sha256:
            raise AIControlValidationError("config_prompt_sha_mismatch")
        receipt = prompt.source_receipt_json
        receipt_sha256 = prompt.source_receipt_sha256
        if receipt is None:
            if receipt_sha256 is not None:
                raise AIControlValidationError("prompt_source_receipt_sha_invalid")
        elif (
            not isinstance(receipt, Mapping)
            or receipt.get("contract_version") != "prompt-source-receipt.v1"
            or not isinstance(receipt_sha256, str)
            or sha256_json(dict(receipt)) != receipt_sha256
        ):
            raise AIControlValidationError("prompt_source_receipt_invalid")
        return content, message_contract, receipt_sha256

    @staticmethod
    def _validate_prompt_message_contract_variables(
        *,
        variables_json: Mapping[str, Any],
        message_contract: Mapping[str, Any] | None,
    ) -> None:
        """Require every structured user-context key to be frozen as a variable."""
        if message_contract is None:
            return
        try:
            required, optional = PromptRenderer.declared_variables(variables_json)
        except PromptRenderError as exc:
            raise AIControlValidationError(str(exc)) from exc
        if not set(message_contract["user_context_keys"]).issubset(required | optional):
            raise AIControlValidationError(
                "config_prompt_message_contract_variable_missing"
            )

    @staticmethod
    def _validate_profile_prompt_contract(
        *,
        profile_key: str,
        variables_json: Mapping[str, Any],
        message_contract: Mapping[str, Any] | None,
        prompt_key: str | None = None,
    ) -> None:
        """Enforce Profile-specific structured context at freeze and replay time."""
        if profile_key == XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1:
            expected_context = [
                "SAFE_STUDY_CONTEXT_JSON",
                "QUALITY_RESULTS_JSON",
                "STUDY_SCREENING_RESULT_JSON",
                "SYSTEM_ANALYSIS_RESULT_JSON",
            ]
            if message_contract is None or message_contract.get(
                "user_context_keys"
            ) != expected_context:
                raise AIControlValidationError(
                    "xray_primary_adjudication_prompt_message_contract_invalid"
                )
            try:
                required, optional = PromptRenderer.declared_variables(
                    variables_json
                )
            except PromptRenderError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if required != {*expected_context, "OUTPUT_SCHEMA_JSON"} or optional:
                raise AIControlValidationError(
                    "xray_primary_adjudication_prompt_variables_invalid"
                )
            return
        if profile_key in {
            XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
            XRAY_IMAGE_QUALITY_PROFILE_V1,
        }:
            if message_contract is None or message_contract.get(
                "user_context_keys"
            ) != ["SAFE_STUDY_CONTEXT_JSON"]:
                raise AIControlValidationError(
                    "anatomy_localization_prompt_message_contract_invalid"
                    if profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
                    else "xray_image_quality_prompt_message_contract_invalid"
                )
            try:
                required, optional = PromptRenderer.declared_variables(
                    variables_json
                )
            except PromptRenderError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if required != {
                "SAFE_STUDY_CONTEXT_JSON",
                "OUTPUT_SCHEMA_JSON",
            } or optional:
                raise AIControlValidationError(
                    "anatomy_localization_prompt_variables_invalid"
                    if profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
                    else "xray_image_quality_prompt_variables_invalid"
                )
            return
        if profile_key == XRAY_REPORT_GENERATION_PROFILE_V1:
            expected_context = [
                "FINAL_MEDICAL_RESULT_JSON",
                "QUALITY_RESULTS_JSON",
                "REPORT_SCHEMA_JSON",
            ]
            if message_contract is None or message_contract.get(
                "user_context_keys"
            ) != expected_context:
                raise AIControlValidationError(
                    "xray_report_generation_prompt_message_contract_invalid"
                )
            try:
                required, optional = PromptRenderer.declared_variables(
                    variables_json
                )
            except PromptRenderError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if required != set(expected_context) or optional:
                raise AIControlValidationError(
                    "xray_report_generation_prompt_variables_invalid"
                )
            return
        if profile_key in {
            XRAY_STUDY_SCREENING_PROFILE_V1,
            XRAY_STUDY_SCREENING_PROFILE_V2,
            XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
        }:
            if message_contract is None or message_contract.get(
                "user_context_keys"
            ) != ["SAFE_STUDY_CONTEXT_JSON", "QUALITY_RESULTS_JSON"]:
                raise AIControlValidationError(
                    "xray_system_analysis_prompt_message_contract_invalid"
                    if profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
                    else "xray_study_screening_prompt_message_contract_invalid"
                )
            try:
                required, optional = PromptRenderer.declared_variables(
                    variables_json
                )
            except PromptRenderError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if required != {
                "SAFE_STUDY_CONTEXT_JSON",
                "QUALITY_RESULTS_JSON",
                "OUTPUT_SCHEMA_JSON",
            } or optional:
                raise AIControlValidationError(
                    "xray_system_analysis_prompt_variables_invalid"
                    if profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
                    else "xray_study_screening_prompt_variables_invalid"
                )
            return
        if profile_key not in {
            "xray_targeted_review_v1",
            XRAY_TARGETED_REVIEW_PROFILE_V2,
        }:
            return
        if prompt_key in _TARGETED_REVIEW_PROMPT_BINDINGS.values():
            expected_context = [
                "SAFE_STUDY_CONTEXT_JSON",
                "PRIMARY_RESULT_JSON",
                "ROUTE_CONTEXT_JSON",
                "QUALITY_RESULTS_JSON",
                "STUDY_SCREENING_RESULT_JSON",
                "SYSTEM_ANALYSIS_RESULT_JSON",
            ]
            if message_contract is None or message_contract.get(
                "user_context_keys"
            ) != expected_context:
                raise AIControlValidationError(
                    "xray_targeted_review_prompt_message_contract_invalid"
                )
            try:
                required, optional = PromptRenderer.declared_variables(variables_json)
            except PromptRenderError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if required != {*expected_context, "OUTPUT_SCHEMA_JSON"} or optional:
                raise AIControlValidationError(
                    "xray_targeted_review_prompt_variables_invalid"
                )
            return
        if message_contract is None:
            raise AIControlValidationError(
                "config_targeted_prompt_message_contract_required"
            )
        user_context_keys = set(message_contract["user_context_keys"])
        required_context = {"SAFE_STUDY_CONTEXT_JSON", "PRIMARY_RESULT_JSON"}
        if not required_context.issubset(user_context_keys):
            raise AIControlValidationError(
                "config_targeted_prompt_primary_result_context_required"
            )
        try:
            required, optional = PromptRenderer.declared_variables(variables_json)
        except PromptRenderError as exc:
            raise AIControlValidationError(str(exc)) from exc
        if "PRIMARY_RESULT_JSON" not in required | optional:
            raise AIControlValidationError(
                "config_targeted_prompt_primary_result_variable_required"
            )

    @staticmethod
    def _validate_localization_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        localization_selected = (
            task_type == XRAY_ANATOMY_LOCALIZATION_TASK_TYPE
            or profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
            or config_key in _ANATOMY_LOCALIZATION_PROMPT_BINDINGS
            or prompt_key in _ANATOMY_LOCALIZATION_PROMPT_BINDINGS.values()
        )
        if not localization_selected:
            return
        expected_prompt_key = _ANATOMY_LOCALIZATION_PROMPT_BINDINGS.get(config_key)
        if (
            modality_type != "xray"
            or task_type != XRAY_ANATOMY_LOCALIZATION_TASK_TYPE
            or profile_key != XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or activation_scope != "global"
            or scope_key != "global"
        ):
            raise AIControlValidationError(
                "anatomy_localization_config_binding_invalid"
            )

    @staticmethod
    def _validate_full_chain_primary_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        primary_selected = (
            profile_key == XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
            or prompt_key in _FULL_CHAIN_PRIMARY_PROMPT_BINDINGS.values()
        )
        if not primary_selected:
            return
        expected_prompt_key = _FULL_CHAIN_PRIMARY_PROMPT_BINDINGS.get(config_key)
        scope_is_valid = (
            activation_scope == "global" and scope_key == "global"
        ) or (
            activation_scope == "experiment"
            and isinstance(scope_key, str)
            and bool(scope_key.strip())
        )
        if (
            modality_type != "xray"
            or task_type != "diagnose"
            or profile_key != XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or not scope_is_valid
        ):
            raise AIControlValidationError(
                "xray_primary_adjudication_config_binding_invalid"
            )

    @staticmethod
    def _validate_image_quality_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        quality_selected = (
            task_type == XRAY_IMAGE_QUALITY_TASK_TYPE
            or profile_key == XRAY_IMAGE_QUALITY_PROFILE_V1
            or config_key in _IMAGE_QUALITY_PROMPT_BINDINGS
            or prompt_key in _IMAGE_QUALITY_PROMPT_BINDINGS.values()
        )
        if not quality_selected:
            return
        expected_prompt_key = _IMAGE_QUALITY_PROMPT_BINDINGS.get(config_key)
        if (
            modality_type != "xray"
            or task_type != XRAY_IMAGE_QUALITY_TASK_TYPE
            or profile_key != XRAY_IMAGE_QUALITY_PROFILE_V1
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or activation_scope != "global"
            or scope_key != "global"
        ):
            raise AIControlValidationError(
                "xray_image_quality_config_binding_invalid"
            )

    @staticmethod
    def _validate_study_screening_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        screening_selected = (
            profile_key
            in {
                XRAY_STUDY_SCREENING_PROFILE_V1,
                XRAY_STUDY_SCREENING_PROFILE_V2,
            }
            or config_key in _STUDY_SCREENING_PROMPT_BINDINGS
            or prompt_key in _STUDY_SCREENING_PROMPT_BINDINGS.values()
        )
        if not screening_selected:
            return
        expected_prompt_key = _STUDY_SCREENING_PROMPT_BINDINGS.get(config_key)
        scope_is_valid = (
            activation_scope == "global" and scope_key == "global"
        ) or (
            activation_scope == "experiment"
            and isinstance(scope_key, str)
            and bool(scope_key.strip())
        )
        if (
            modality_type != "xray"
            or (
                profile_key == XRAY_STUDY_SCREENING_PROFILE_V1
                and task_type != "diagnose"
            )
            or (
                profile_key == XRAY_STUDY_SCREENING_PROFILE_V2
                and task_type
                not in {"diagnose", XRAY_STUDY_SCREENING_TASK_TYPE}
            )
            or profile_key
            not in {
                XRAY_STUDY_SCREENING_PROFILE_V1,
                XRAY_STUDY_SCREENING_PROFILE_V2,
            }
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or not scope_is_valid
        ):
            raise AIControlValidationError(
                "xray_study_screening_config_binding_invalid"
            )

    @staticmethod
    def _validate_system_analysis_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        analysis_selected = (
            task_type == XRAY_SYSTEM_ANALYSIS_TASK_TYPE
            or profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
            or config_key in _SYSTEM_ANALYSIS_PROMPT_BINDINGS
            or prompt_key in _SYSTEM_ANALYSIS_PROMPT_BINDINGS.values()
        )
        if not analysis_selected:
            return
        expected_prompt_key = _SYSTEM_ANALYSIS_PROMPT_BINDINGS.get(config_key)
        scope_is_valid = (
            activation_scope == "global" and scope_key == "global"
        ) or (
            activation_scope == "experiment"
            and isinstance(scope_key, str)
            and bool(scope_key.strip())
        )
        if (
            modality_type != "xray"
            or task_type not in {"diagnose", XRAY_SYSTEM_ANALYSIS_TASK_TYPE}
            or profile_key != XRAY_SYSTEM_ANALYSIS_PROFILE_V1
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or not scope_is_valid
        ):
            raise AIControlValidationError(
                "xray_system_analysis_config_binding_invalid"
            )

    @staticmethod
    def _validate_report_generation_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        report_selected = (
            profile_key == XRAY_REPORT_GENERATION_PROFILE_V1
            or config_key in _REPORT_GENERATION_PROMPT_BINDINGS
            or prompt_key in _REPORT_GENERATION_PROMPT_BINDINGS.values()
        )
        if not report_selected:
            return
        expected_prompt_key = _REPORT_GENERATION_PROMPT_BINDINGS.get(config_key)
        scope_is_valid = (
            activation_scope == "global" and scope_key == "global"
        ) or (
            activation_scope == "experiment"
            and isinstance(scope_key, str)
            and bool(scope_key.strip())
        )
        if (
            modality_type != "xray"
            or task_type != "diagnose"
            or profile_key != XRAY_REPORT_GENERATION_PROFILE_V1
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or not scope_is_valid
        ):
            raise AIControlValidationError(
                "xray_report_generation_config_binding_invalid"
            )

    @staticmethod
    def _validate_targeted_review_source_binding(
        *,
        config_key: Any,
        modality_type: Any,
        task_type: Any,
        profile_key: Any,
        activation_scope: Any,
        scope_key: Any,
        prompt_key: Any,
    ) -> None:
        targeted_selected = (
            config_key in _TARGETED_REVIEW_PROMPT_BINDINGS
            or prompt_key in _TARGETED_REVIEW_PROMPT_BINDINGS.values()
        )
        if not targeted_selected:
            return
        expected_prompt_key = _TARGETED_REVIEW_PROMPT_BINDINGS.get(config_key)
        if (
            modality_type != "xray"
            or task_type != "diagnose"
            or profile_key != XRAY_TARGETED_REVIEW_PROFILE_V2
            or expected_prompt_key is None
            or prompt_key != expected_prompt_key
            or activation_scope != "experiment"
            or not isinstance(scope_key, str)
            or not scope_key.strip()
        ):
            raise AIControlValidationError(
                "xray_targeted_review_config_binding_invalid"
            )

    @staticmethod
    def _validated_lane_plan(pool: AIModelPool) -> dict[str, Any]:
        if (
            pool.execution_mode != "single"
            or pool.winner_policy != "single"
            or pool.lane_count != 1
        ):
            raise AIControlValidationError("config_pool_single_lane_required")
        try:
            plan = ModelPoolLanePlanContract.model_validate(pool.lane_plan_json)
        except ValueError as exc:
            raise AIControlValidationError("config_pool_lane_contract_invalid") from exc
        normalized = plan.model_dump(mode="json")
        lanes = normalized.get("lanes")
        if not isinstance(lanes, list) or len(lanes) != 1:
            raise AIControlValidationError("config_pool_single_lane_required")
        expected_sha = sha256_json(
            {
                "pool_key": pool.pool_key,
                "version": pool.version,
                "execution_mode": pool.execution_mode,
                "winner_policy": pool.winner_policy,
                "lane_count": pool.lane_count,
                "lane_plan_json": normalized,
            }
        )
        if expected_sha != pool.pool_sha256:
            raise AIControlValidationError("config_pool_sha_mismatch")
        return normalized

    @staticmethod
    def _required_logical_calls(compiled_pipeline: Mapping[str, Any]) -> int:
        stages = compiled_pipeline.get("stages")
        dynamic = compiled_pipeline.get("dynamic_stage_definitions")
        if not isinstance(stages, list) or not isinstance(dynamic, list):
            raise AIControlValidationError("compiled_pipeline_contract_invalid")
        required = sum(
            1
            for stage in stages
            if isinstance(stage, Mapping) and stage.get("provider_required") is True
        )
        for stage in dynamic:
            if not isinstance(stage, Mapping):
                raise AIControlValidationError("compiled_pipeline_contract_invalid")
            if stage.get("provider_required") is True:
                max_instances = stage.get("max_instances")
                if not isinstance(max_instances, int) or max_instances < 0:
                    raise AIControlValidationError(
                        "compiled_pipeline_dynamic_limit_invalid"
                    )
                required += max_instances
        return required

    @staticmethod
    def _validate_budget(
        *,
        budget_policy: dict[str, Any],
        prompt_content: str,
        lane: Mapping[str, Any],
        capability: Mapping[str, Any],
        required_logical_calls: int,
        xray_image_contract_required: bool = False,
        exact_single_call_attempt_required: bool = False,
        exact_single_call_error_code: str = (
            "anatomy_localization_single_call_budget_required"
        ),
    ) -> None:
        try:
            budget = BudgetPolicyContract.model_validate(budget_policy)
        except ValueError as exc:
            raise AIControlValidationError("config_budget_contract_invalid") from exc
        normalized = budget.model_dump(mode="json")
        if len(prompt_content) > normalized["max_prompt_chars"]:
            raise AIControlValidationError("config_prompt_budget_exceeded")
        if not capability.get("supports_images") or not capability.get(
            "supports_json_schema"
        ):
            raise AIControlValidationError("config_connection_capability_required")
        max_images = capability.get("max_input_images")
        max_context_tokens = capability.get("max_context_tokens")
        if not isinstance(max_images, int) or not isinstance(max_context_tokens, int):
            raise AIControlValidationError("config_connection_capability_invalid")
        if xray_image_contract_required:
            if normalized["max_input_images"] != XRAY_STUDY_MAX_IMAGE_COUNT:
                raise AIControlValidationError("config_xray_image_budget_invalid")
            if max_images < XRAY_STUDY_MAX_IMAGE_COUNT:
                raise AIControlValidationError(
                    "config_xray_connection_image_capability_invalid"
                )
        if normalized["max_input_images"] > max_images:
            raise AIControlValidationError("config_image_budget_exceeds_connection")
        if normalized["max_total_calls"] < required_logical_calls:
            raise AIControlValidationError("config_call_budget_exceeded")
        if exact_single_call_attempt_required and (
            required_logical_calls != 1
            or normalized["max_total_calls"] != 1
            or normalized["max_total_attempts"] != 1
        ):
            raise AIControlValidationError(
                exact_single_call_error_code
            )
        max_attempts = lane.get("max_attempts")
        timeout_ms = lane.get("timeout_ms")
        generation = lane.get("generation_params")
        if (
            not isinstance(max_attempts, int)
            or max_attempts != 1
            or max_attempts > normalized["max_total_attempts"]
        ):
            raise AIControlValidationError("config_attempt_budget_exceeded")
        if (
            not isinstance(timeout_ms, int)
            or timeout_ms > normalized["task_deadline_ms"]
        ):
            raise AIControlValidationError("config_lane_timeout_exceeds_deadline")
        if not isinstance(generation, Mapping):
            raise AIControlValidationError("config_generation_params_invalid")
        max_output_tokens = generation.get("max_output_tokens")
        if (
            not isinstance(max_output_tokens, int)
            or max_output_tokens < 1
            or max_output_tokens > max_context_tokens
        ):
            raise AIControlValidationError("config_output_token_capability_exceeded")

    def compile(
        self,
        *,
        source: Mapping[str, Any],
        prompt: AIPromptTemplate,
        pool: AIModelPool,
        connections: Sequence[AIAPIConnection],
        require_validated_sources: bool,
    ) -> CompiledAIConfig:
        """Compile a deterministic snapshot from checked source rows.

        ``source`` is intentionally constrained to the fields in
        :class:`AIConfigCreate` or an existing v2 Config.  The compiler never
        accepts a raw provider plan, raw Schema, compiled output or Prompt text
        from an HTTP caller.
        """
        if (
            prompt.id != source["prompt_template_id"]
            or pool.id != source["model_pool_id"]
        ):
            raise AIControlValidationError("config_source_id_mismatch")
        self._validate_localization_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        self._validate_full_chain_primary_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        self._validate_image_quality_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        self._validate_study_screening_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        self._validate_system_analysis_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        self._validate_targeted_review_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        self._validate_report_generation_source_binding(
            config_key=source["config_key"],
            modality_type=source["modality_type"],
            task_type=source["task_type"],
            profile_key=source["profile_key"],
            activation_scope=source["activation_scope"],
            scope_key=source["scope_key"],
            prompt_key=prompt.prompt_key,
        )
        if require_validated_sources:
            if pool.status != "validated":
                raise AIControlValidationError("config_pool_validated_required")
        elif pool.status not in {"validated", "retired"}:
            raise AIControlValidationError("config_pool_history_state_invalid")

        (
            prompt_content,
            prompt_message_contract,
            prompt_source_receipt_sha256,
        ) = self._validate_prompt(prompt, require_validated=require_validated_sources)
        self._validate_profile_prompt_contract(
            profile_key=str(source["profile_key"]),
            variables_json=prompt.variables_json,
            message_contract=prompt_message_contract,
            prompt_key=prompt.prompt_key,
        )
        lane_plan = self._validated_lane_plan(pool)
        lanes = lane_plan["lanes"]
        if len(connections) != len(lanes):
            raise AIControlValidationError("config_connection_binding_missing")
        connection_by_id = {item.id: item for item in connections}
        model_lanes: list[dict[str, Any]] = []
        capabilities: list[Mapping[str, Any]] = []
        for lane in lanes:
            connection_id = lane["connection_id"]
            connection = connection_by_id.get(connection_id)
            if connection is None:
                raise AIControlValidationError("config_connection_not_found")
            if require_validated_sources:
                if connection.status != "validated":
                    raise AIControlValidationError(
                        "config_connection_validated_required"
                    )
            elif connection.status not in {"validated", "retired"}:
                raise AIControlValidationError(
                    "config_connection_history_state_invalid"
                )
            try:
                canonical_base_url = canonicalize_connection_base_url(
                    connection.base_url
                )
                expected_connection_sha = canonical_connection_metadata_sha256(
                    {
                        "connection_key": connection.connection_key,
                        "version": connection.version,
                        "provider_type": connection.provider_type,
                        "api_format": connection.api_format,
                        "base_url": connection.base_url,
                        "region": connection.region,
                        "capability_json": connection.capability_json,
                    }
                )
            except ConnectionContractError as exc:
                raise AIControlValidationError(str(exc)) from exc
            if canonical_base_url != connection.base_url:
                raise AIControlValidationError(
                    "config_connection_base_url_not_canonical"
                )
            if (
                expected_connection_sha != connection.connection_sha256
                or lane["connection_sha256"] != expected_connection_sha
            ):
                raise AIControlValidationError("config_connection_sha_mismatch")
            capability = connection.capability_json
            if (
                not isinstance(capability, Mapping)
                or capability.get("contract_version") != "connection-capability.v1"
            ):
                raise AIControlValidationError("config_connection_capability_invalid")
            try:
                gateway_profile = normalize_gateway_profile(
                    capability.get("gateway_profile")
                )
            except GatewayContractError as exc:
                raise AIControlValidationError(str(exc)) from exc
            capabilities.append(
                {**dict(capability), "gateway_profile": gateway_profile}
            )
            model_lanes.append(
                {
                    "lane_key": lane["lane_key"],
                    "priority": lane["priority"],
                    "connection_id": connection.id,
                    "connection_key": connection.connection_key,
                    "connection_version": connection.version,
                    "connection_sha256": connection.connection_sha256,
                    "provider_type": connection.provider_type,
                    "api_format": connection.api_format,
                    "base_url": connection.base_url,
                    "requested_model": lane["requested_model"],
                    "timeout_ms": lane["timeout_ms"],
                    "max_attempts": lane["max_attempts"],
                    "generation_params": lane["generation_params"],
                }
            )

        try:
            compiled_pipeline, compiled_pipeline_sha256 = compile_profile_contract(
                str(source["profile_key"]), self.registry
            )
        except PipelineContractError as exc:
            raise AIControlValidationError(str(exc)) from exc
        if not compiled_pipeline.get("stages"):
            raise AIControlValidationError("compiled_pipeline_empty")

        budget_policy = dict(source["budget_policy_json"])
        # Phase A-C has exactly one lane, so the capability requirements are
        # evaluated against the sole frozen connection.
        self._validate_budget(
            budget_policy=budget_policy,
            prompt_content=prompt_content,
            lane=model_lanes[0],
            capability=capabilities[0],
            required_logical_calls=self._required_logical_calls(compiled_pipeline),
            xray_image_contract_required=(
                requires_exact_xray_five_image_config_contract(
                    modality_type=source["modality_type"],
                    task_type=source["task_type"],
                    profile_key=source["profile_key"],
                )
            ),
            exact_single_call_attempt_required=(
                source["profile_key"]
                in {
                    XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
                    XRAY_IMAGE_QUALITY_PROFILE_V1,
                    XRAY_STUDY_SCREENING_PROFILE_V2,
                    XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
                    XRAY_REPORT_GENERATION_PROFILE_V1,
                }
            ),
            exact_single_call_error_code=(
                "xray_image_quality_single_call_budget_required"
                if source["profile_key"] == XRAY_IMAGE_QUALITY_PROFILE_V1
                else (
                    "xray_study_screening_single_call_budget_required"
                    if source["profile_key"] == XRAY_STUDY_SCREENING_PROFILE_V2
                    else (
                        "xray_system_analysis_single_call_budget_required"
                        if source["profile_key"]
                        == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
                        else (
                            "xray_report_generation_single_call_budget_required"
                            if source["profile_key"]
                            == XRAY_REPORT_GENERATION_PROFILE_V1
                            else "anatomy_localization_single_call_budget_required"
                        )
                    )
                )
            ),
        )

        model_snapshot = {
            "contract_version": "ai-model-snapshot.v1",
            "execution_mode": "single",
            "winner_policy": "single",
            "lanes": model_lanes,
        }
        output_schema = self._output_schema(profile_key=str(source["profile_key"]))
        gateway_profile = dict(capabilities[0]["gateway_profile"])
        capability_manifest = {
            "contract_version": "ai-capability-manifest.v1",
            "provider_disabled": not gateway_profile["provider_enabled"],
            "gateway_profile_sha256": sha256_json(gateway_profile),
            "execution_mode": "single",
            "winner_policy": "single",
            "lane_count": 1,
            "supports_images": bool(capabilities[0]["supports_images"]),
            "supports_json_schema": bool(capabilities[0]["supports_json_schema"]),
            "max_input_images": capabilities[0]["max_input_images"],
            "max_context_tokens": capabilities[0]["max_context_tokens"],
            "profile_key": source["profile_key"],
        }
        prompt_sha = sha256_text(prompt_content)
        model_snapshot_sha = sha256_json(model_snapshot)
        output_schema_sha = sha256_json(output_schema)
        capability_manifest_sha = sha256_json(capability_manifest)
        budget_policy_sha = sha256_json(budget_policy)
        config_body = {
            "config_contract_version": AI_CONFIG_V2,
            "config_key": source["config_key"],
            "version": source["version"],
            "modality_type": source["modality_type"],
            "task_type": source["task_type"],
            "profile_key": source["profile_key"],
            "activation_scope": source["activation_scope"],
            "scope_key": source["scope_key"],
            "prompt": {
                "prompt_template_id": prompt.id,
                "prompt_key": prompt.prompt_key,
                "prompt_version": prompt.version,
                "content": prompt_content,
                "variables_json": prompt.variables_json,
                "content_sha256": prompt_sha,
                "message_contract_json": prompt_message_contract,
                "source_receipt_sha256": prompt_source_receipt_sha256,
            },
            "model_pool": {
                "model_pool_id": pool.id,
                "model_pool_key": pool.pool_key,
                "model_pool_version": pool.version,
            },
            "model": model_snapshot,
            "output_schema": output_schema,
            "gateway_profile": gateway_profile,
            "compiled_pipeline": compiled_pipeline,
            "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "capability_manifest": capability_manifest,
            "budget_policy": budget_policy,
        }
        config_sha256 = sha256_json(config_body)
        release_fingerprint = sha256_json(
            {
                "prompt_content_sha256": prompt_sha,
                "prompt_message_contract_sha256": sha256_json(prompt_message_contract)
                if prompt_message_contract is not None
                else None,
                "prompt_source_receipt_sha256": prompt_source_receipt_sha256,
                "model_snapshot_sha256": model_snapshot_sha,
                "gateway_profile_sha256": sha256_json(gateway_profile),
                "output_schema_sha256": output_schema_sha,
                "compiled_pipeline_sha256": compiled_pipeline_sha256,
                "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
                "capability_manifest_sha256": capability_manifest_sha,
                "budget_policy_sha256": budget_policy_sha,
            }
        )
        values = {
            "config_contract_version": AI_CONFIG_V2,
            "config_key": source["config_key"],
            "version": source["version"],
            "name": source["name"],
            "modality_type": source["modality_type"],
            "task_type": source["task_type"],
            "profile_key": source["profile_key"],
            "activation_scope": source["activation_scope"],
            "scope_key": source["scope_key"],
            "activation_slot": None,
            "prompt_template_id": prompt.id,
            "prompt_key": prompt.prompt_key,
            "prompt_version": prompt.version,
            "prompt_content": prompt_content,
            "prompt_variables_json": dict(prompt.variables_json),
            "prompt_content_sha256": prompt_sha,
            "prompt_message_contract_json": prompt_message_contract,
            "prompt_source_receipt_sha256": prompt_source_receipt_sha256,
            "model_pool_id": pool.id,
            "model_pool_key": pool.pool_key,
            "model_pool_version": pool.version,
            "model_snapshot_json": model_snapshot,
            "model_snapshot_sha256": model_snapshot_sha,
            "output_schema_json": output_schema,
            "output_schema_sha256": output_schema_sha,
            "gateway_profile_json": gateway_profile,
            "capability_manifest_json": capability_manifest,
            "compiled_pipeline_json": compiled_pipeline,
            "compiled_pipeline_sha256": compiled_pipeline_sha256,
            "stage_registry_contract_version": self.registry.CONTRACT_VERSION,
            "budget_policy_json": budget_policy,
            "config_sha256": config_sha256,
            "release_fingerprint": release_fingerprint,
        }
        return CompiledAIConfig(
            values=values,
            capability_manifest_sha256=capability_manifest_sha,
            budget_policy_sha256=budget_policy_sha,
        )

    def verify_frozen_integrity(self, config: Any) -> None:
        """Check v2 snapshot self-consistency without reading mutable sources."""
        required = (
            "prompt_template_id",
            "prompt_key",
            "prompt_version",
            "prompt_content",
            "prompt_variables_json",
            "prompt_content_sha256",
            "model_pool_id",
            "model_pool_key",
            "model_pool_version",
            "model_snapshot_json",
            "model_snapshot_sha256",
            "output_schema_json",
            "output_schema_sha256",
            "compiled_pipeline_json",
            "compiled_pipeline_sha256",
            "stage_registry_contract_version",
            "capability_manifest_json",
            "budget_policy_json",
            "config_sha256",
            "release_fingerprint",
        )
        if any(getattr(config, field, None) is None for field in required):
            raise AIControlValidationError("config_v2_snapshot_missing")
        try:
            normalized = PromptRenderer.validate_template(
                content=config.prompt_content,
                variables_json=config.prompt_variables_json,
            )
        except PromptRenderError as exc:
            raise AIControlValidationError(str(exc)) from exc
        if sha256_text(normalized) != config.prompt_content_sha256:
            raise AIControlValidationError("config_prompt_snapshot_sha_mismatch")
        if sha256_json(config.model_snapshot_json) != config.model_snapshot_sha256:
            raise AIControlValidationError("config_model_snapshot_sha_mismatch")
        if sha256_json(config.output_schema_json) != config.output_schema_sha256:
            raise AIControlValidationError("config_schema_snapshot_sha_mismatch")
        self._validate_localization_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        self._validate_full_chain_primary_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        self._validate_image_quality_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        self._validate_study_screening_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        self._validate_system_analysis_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        self._validate_targeted_review_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        self._validate_report_generation_source_binding(
            config_key=config.config_key,
            modality_type=config.modality_type,
            task_type=config.task_type,
            profile_key=config.profile_key,
            activation_scope=config.activation_scope,
            scope_key=config.scope_key,
            prompt_key=config.prompt_key,
        )
        if (
            config.profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
            and config.output_schema_json
            != self._output_schema(profile_key=config.profile_key)
        ):
            raise AIControlValidationError(
                "anatomy_localization_schema_snapshot_mismatch"
            )
        if (
            config.profile_key == XRAY_IMAGE_QUALITY_PROFILE_V1
            and config.output_schema_json
            != self._output_schema(profile_key=config.profile_key)
        ):
            raise AIControlValidationError(
                "xray_image_quality_schema_snapshot_mismatch"
            )
        if (
            config.profile_key
            in {
                XRAY_STUDY_SCREENING_PROFILE_V1,
                XRAY_STUDY_SCREENING_PROFILE_V2,
            }
            and config.output_schema_json
            != self._output_schema(profile_key=config.profile_key)
        ):
            raise AIControlValidationError(
                "xray_study_screening_schema_snapshot_mismatch"
            )
        if (
            config.profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
            and config.output_schema_json
            != self._output_schema(profile_key=config.profile_key)
        ):
            raise AIControlValidationError(
                "xray_system_analysis_schema_snapshot_mismatch"
            )
        if (
            config.profile_key == XRAY_REPORT_GENERATION_PROFILE_V1
            and config.output_schema_json
            != self._output_schema(profile_key=config.profile_key)
        ):
            raise AIControlValidationError(
                "xray_report_generation_schema_snapshot_mismatch"
            )
        try:
            pipeline, pipeline_sha = compile_profile_contract(
                config.profile_key, self.registry
            )
        except PipelineContractError as exc:
            raise AIControlValidationError(str(exc)) from exc
        if (
            pipeline != config.compiled_pipeline_json
            or pipeline_sha != config.compiled_pipeline_sha256
        ):
            raise AIControlValidationError("config_pipeline_snapshot_mismatch")
        if config.stage_registry_contract_version != self.registry.CONTRACT_VERSION:
            raise AIControlValidationError("config_registry_contract_mismatch")
        model_snapshot = config.model_snapshot_json
        if (
            not isinstance(model_snapshot, Mapping)
            or model_snapshot.get("contract_version") != "ai-model-snapshot.v1"
            or model_snapshot.get("execution_mode") != "single"
            or model_snapshot.get("winner_policy") != "single"
            or not isinstance(model_snapshot.get("lanes"), list)
            or len(model_snapshot["lanes"]) != 1
        ):
            raise AIControlValidationError("config_model_snapshot_contract_invalid")
        lane = model_snapshot["lanes"][0]
        if not isinstance(lane, Mapping):
            raise AIControlValidationError("config_model_snapshot_contract_invalid")
        self._validate_budget(
            budget_policy=dict(config.budget_policy_json),
            prompt_content=normalized,
            lane=lane,
            capability={
                "supports_images": config.capability_manifest_json.get(
                    "supports_images"
                ),
                "supports_json_schema": config.capability_manifest_json.get(
                    "supports_json_schema"
                ),
                "max_input_images": config.capability_manifest_json.get(
                    "max_input_images"
                ),
                "max_context_tokens": config.capability_manifest_json.get(
                    "max_context_tokens"
                ),
            },
            required_logical_calls=self._required_logical_calls(
                config.compiled_pipeline_json
            ),
            xray_image_contract_required=(
                requires_exact_xray_five_image_config_contract(
                    modality_type=config.modality_type,
                    task_type=config.task_type,
                    profile_key=config.profile_key,
                )
            ),
            exact_single_call_attempt_required=(
                config.profile_key
                in {
                    XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
                    XRAY_IMAGE_QUALITY_PROFILE_V1,
                    XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
                    XRAY_REPORT_GENERATION_PROFILE_V1,
                }
            ),
            exact_single_call_error_code=(
                "xray_image_quality_single_call_budget_required"
                if config.profile_key == XRAY_IMAGE_QUALITY_PROFILE_V1
                else (
                    "xray_system_analysis_single_call_budget_required"
                    if config.profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
                    else (
                        "xray_report_generation_single_call_budget_required"
                        if config.profile_key
                        == XRAY_REPORT_GENERATION_PROFILE_V1
                        else "anatomy_localization_single_call_budget_required"
                    )
                )
            ),
        )
        gateway_profile_raw = getattr(config, "gateway_profile_json", None)
        config_body = {
            "config_contract_version": config.config_contract_version,
            "config_key": config.config_key,
            "version": config.version,
            "modality_type": config.modality_type,
            "task_type": config.task_type,
            "profile_key": config.profile_key,
            "activation_scope": config.activation_scope,
            "scope_key": config.scope_key,
            "prompt": {
                "prompt_template_id": config.prompt_template_id,
                "prompt_key": config.prompt_key,
                "prompt_version": config.prompt_version,
                "content": normalized,
                "variables_json": config.prompt_variables_json,
                "content_sha256": config.prompt_content_sha256,
            },
            "model_pool": {
                "model_pool_id": config.model_pool_id,
                "model_pool_key": config.model_pool_key,
                "model_pool_version": config.model_pool_version,
            },
            "model": config.model_snapshot_json,
            "output_schema": config.output_schema_json,
            "compiled_pipeline": config.compiled_pipeline_json,
            "stage_registry_contract_version": config.stage_registry_contract_version,
            "capability_manifest": config.capability_manifest_json,
            "budget_policy": config.budget_policy_json,
        }
        if gateway_profile_raw is None:
            # Existing ai-config.v2 rows were frozen before Prompt Runtime/Gateway
            # fields existed.  Preserve their content hash and disabled semantics.
            if config.capability_manifest_json.get("provider_disabled") is not True:
                raise AIControlValidationError("provider_disabled_required")
            gateway_profile = None
        else:
            try:
                gateway_profile = normalize_gateway_profile(gateway_profile_raw)
                prompt_message_contract = validate_prompt_message_template(
                    content=normalized,
                    message_contract_json=getattr(
                        config, "prompt_message_contract_json", None
                    ),
                )
            except (GatewayContractError, PromptMessageContractError) as exc:
                raise AIControlValidationError(str(exc)) from exc
            self._validate_prompt_message_contract_variables(
                variables_json=config.prompt_variables_json,
                message_contract=prompt_message_contract,
            )
            self._validate_profile_prompt_contract(
                profile_key=str(config.profile_key),
                variables_json=config.prompt_variables_json,
                message_contract=prompt_message_contract,
                prompt_key=config.prompt_key,
            )
            receipt_sha256 = getattr(config, "prompt_source_receipt_sha256", None)
            if receipt_sha256 is not None and (
                not isinstance(receipt_sha256, str) or len(receipt_sha256) != 64
            ):
                raise AIControlValidationError("prompt_source_receipt_sha_invalid")
            if config.capability_manifest_json.get("provider_disabled") is not (
                not gateway_profile["provider_enabled"]
            ) or config.capability_manifest_json.get(
                "gateway_profile_sha256"
            ) != sha256_json(gateway_profile):
                raise AIControlValidationError(
                    "config_gateway_profile_snapshot_mismatch"
                )
            config_body["prompt"].update(
                {
                    "message_contract_json": prompt_message_contract,
                    "source_receipt_sha256": receipt_sha256,
                }
            )
            config_body["gateway_profile"] = gateway_profile
        if sha256_json(config_body) != config.config_sha256:
            raise AIControlValidationError("config_sha_mismatch")
        release_body = {
            "prompt_content_sha256": config.prompt_content_sha256,
            "model_snapshot_sha256": config.model_snapshot_sha256,
            "output_schema_sha256": config.output_schema_sha256,
            "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
            "stage_registry_contract_version": config.stage_registry_contract_version,
            "capability_manifest_sha256": sha256_json(config.capability_manifest_json),
            "budget_policy_sha256": sha256_json(config.budget_policy_json),
        }
        if gateway_profile is not None:
            release_body.update(
                {
                    "prompt_message_contract_sha256": sha256_json(
                        prompt_message_contract
                    )
                    if prompt_message_contract is not None
                    else None,
                    "prompt_source_receipt_sha256": receipt_sha256,
                    "gateway_profile_sha256": sha256_json(gateway_profile),
                }
            )
        release_fingerprint = sha256_json(release_body)
        if release_fingerprint != config.release_fingerprint:
            raise AIControlValidationError("release_fingerprint_mismatch")


__all__ = ["AIConfigCompiler", "CompiledAIConfig"]
