"""Static stage contracts and fixed zero-model profile compilation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


class PipelineContractError(ValueError):
    pass


@dataclass(frozen=True)
class StageDefinition:
    stage_key: str
    handler_key: str
    handler_version: str
    provider_required: bool


@dataclass(frozen=True)
class StageContext:
    task_id: str
    checkpoint_id: str
    study_revision_id: str
    image_manifest_sha256: str
    trace_id: str


@dataclass(frozen=True)
class StageResult:
    status: str
    output: dict[str, Any]
    error_code: str | None = None


class StageRegistry:
    CONTRACT_VERSION = "stage-contract.v1"

    def __init__(self):
        self._definitions: dict[tuple[str, str], StageDefinition] = {}

    def register(self, definition: StageDefinition) -> None:
        key = (definition.handler_key, definition.handler_version)
        if not all(key) or key in self._definitions:
            raise PipelineContractError("stage_registry_registration_invalid")
        self._definitions[key] = definition

    def resolve(self, *, handler_key: str, handler_version: str) -> StageDefinition:
        definition = self._definitions.get((handler_key, handler_version))
        if definition is None:
            raise PipelineContractError("stage_handler_not_registered")
        return definition


ZERO_MODEL_PROFILE = "zero_model_replay_v1"
XRAY_PRIMARY_PROFILE_V2 = "xray_primary_v2"
XRAY_TARGETED_REVIEW_PROFILE_V2 = "xray_targeted_review_v2"


def build_default_registry() -> StageRegistry:
    registry = StageRegistry()
    registry.register(
        StageDefinition("study_preparation", "study_preparation", "v1", False)
    )
    registry.register(
        StageDefinition("joint_primary_reader", "joint_primary_reader", "v1", True)
    )
    registry.register(StageDefinition("family_routing", "family_routing", "v1", False))
    registry.register(StageDefinition("targeted_review", "targeted_review", "v1", True))
    registry.register(
        StageDefinition("decision_finalization", "decision_finalization", "v1", False)
    )
    registry.register(
        StageDefinition("joint_primary_reader", "joint_primary_reader", "v2", True)
    )
    registry.register(StageDefinition("family_routing", "family_routing", "v2", False))
    registry.register(StageDefinition("targeted_review", "targeted_review", "v2", True))
    registry.register(
        StageDefinition("decision_finalization", "decision_finalization", "v2", False)
    )
    return registry


def compile_profile_contract(
    profile_key: str, registry: StageRegistry
) -> tuple[dict[str, Any], str]:
    paths = {
        ZERO_MODEL_PROFILE: [("study_preparation", "v1")],
        "xray_primary_v1": [
            ("study_preparation", "v1"),
            ("joint_primary_reader", "v1"),
            ("decision_finalization", "v1"),
        ],
        XRAY_PRIMARY_PROFILE_V2: [
            ("study_preparation", "v1"),
            ("joint_primary_reader", "v2"),
            ("decision_finalization", "v2"),
        ],
        # TargetedReview is conditionally materialized by FamilyRouting at
        # runtime.  It is not a static mandatory node in the compiled path.
        "xray_targeted_review_v1": [
            ("study_preparation", "v1"),
            ("joint_primary_reader", "v1"),
            ("family_routing", "v1"),
            ("decision_finalization", "v1"),
        ],
        XRAY_TARGETED_REVIEW_PROFILE_V2: [
            ("study_preparation", "v1"),
            ("joint_primary_reader", "v2"),
            ("family_routing", "v2"),
            ("decision_finalization", "v2"),
        ],
    }
    requested = paths.get(profile_key)
    if requested is None:
        raise PipelineContractError("profile_not_registered")
    definitions = [
        registry.resolve(handler_key=key, handler_version=version)
        for key, version in requested
    ]
    if profile_key == ZERO_MODEL_PROFILE and any(
        item.provider_required for item in definitions
    ):
        raise PipelineContractError("zero_model_profile_provider_forbidden")
    contract: dict[str, Any] = {
        "profile_key": profile_key,
        "stages": [
            {
                "stage_key": item.stage_key,
                "handler_key": item.handler_key,
                "handler_version": item.handler_version,
                "provider_required": item.provider_required,
            }
            for item in definitions
        ],
        "conditional_edges": [],
        "dynamic_stage_definitions": [],
    }
    if profile_key in {"xray_targeted_review_v1", XRAY_TARGETED_REVIEW_PROFILE_V2}:
        targeted_version = (
            "v2" if profile_key == XRAY_TARGETED_REVIEW_PROFILE_V2 else "v1"
        )
        targeted = registry.resolve(
            handler_key="targeted_review", handler_version=targeted_version
        )
        contract["conditional_edges"] = [
            {
                "from": "family_routing",
                "signal": "primary_final",
                "to": "decision_finalization",
            },
            {
                "from": "family_routing",
                "signal": "targeted_review",
                "to": "targeted_review",
            },
            {
                "from": "targeted_review",
                "signal": "completed",
                "to": "decision_finalization",
            },
        ]
        contract["dynamic_stage_definitions"] = [
            {
                "stage_key": targeted.stage_key,
                "handler_key": targeted.handler_key,
                "handler_version": targeted.handler_version,
                "provider_required": targeted.provider_required,
                "max_instances": 1,
            }
        ]
    digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return contract, digest


def compile_profile(
    profile_key: str, registry: StageRegistry
) -> tuple[list[StageDefinition], str]:
    contract, digest = compile_profile_contract(profile_key, registry)
    definitions = [
        registry.resolve(
            handler_key=item["handler_key"], handler_version=item["handler_version"]
        )
        for item in contract["stages"]
    ]
    return definitions, digest


__all__ = [
    "PipelineContractError",
    "StageContext",
    "StageDefinition",
    "StageRegistry",
    "StageResult",
    "ZERO_MODEL_PROFILE",
    "XRAY_PRIMARY_PROFILE_V2",
    "XRAY_TARGETED_REVIEW_PROFILE_V2",
    "build_default_registry",
    "compile_profile",
    "compile_profile_contract",
]
