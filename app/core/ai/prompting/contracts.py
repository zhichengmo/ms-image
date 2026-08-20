"""Immutable Prompt catalog and compiled-call contracts for target XRay AI."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


PROMPT_LANGUAGE = "zh-CN"
PRIMARY_FAMILY_ORDER = (
    "thoracic",
    "abdominal",
    "appendicular_orthopedic",
    "axial_orthopedic",
    "head_neck",
)
PROMPT_ROLES = frozenset(
    {
        "joint_primary_base",
        "joint_primary_module",
        "targeted_focus",
        "review_strategy",
        "technical_evidence",
        "offline_evaluation",
    }
)


class PromptContractError(ValueError):
    pass


@dataclass(frozen=True)
class PromptAsset:
    prompt_key: str
    prompt_role: str
    language: str
    content: str
    content_sha256: str
    family_key: str | None
    report_domain_keys: tuple[str, ...]
    focus_key: str | None
    strategy_key: str | None
    species: str
    input_scope: str
    output_contract: str
    eligibility: str
    status: str

    def __post_init__(self) -> None:
        if self.prompt_role not in PROMPT_ROLES:
            raise PromptContractError("prompt_role_not_registered")
        if self.language != PROMPT_LANGUAGE:
            raise PromptContractError("prompt_language_not_available")
        if not self.prompt_key or not self.content.strip():
            raise PromptContractError("prompt_asset_invalid")
        if self.content_sha256 != sha256_text(self.content):
            raise PromptContractError("prompt_checksum_mismatch")
        if self.status != "published":
            raise PromptContractError("prompt_asset_not_published")


@dataclass(frozen=True)
class SchemaAsset:
    schema_key: str
    schema_version: str
    language: str
    schema: dict[str, Any]
    schema_sha256: str
    output_contract: str
    status: str

    def __post_init__(self) -> None:
        if self.language != PROMPT_LANGUAGE:
            raise PromptContractError("schema_language_not_available")
        if self.status != "published" or not self.schema_key:
            raise PromptContractError("schema_asset_not_published")
        if self.schema_sha256 != sha256_json(self.schema):
            raise PromptContractError("schema_checksum_mismatch")


@dataclass(frozen=True)
class PromptBundle:
    bundle_version: str
    catalog_revision: str
    language: str
    primary_assets: tuple[PromptAsset, ...]
    targeted_assets: tuple[PromptAsset, ...]
    offline_assets: tuple[PromptAsset, ...]
    schema: SchemaAsset
    bundle_sha256: str


@dataclass(frozen=True)
class CompiledPrompt:
    prompt_kind: str
    rendered_text: str
    rendered_sha256: str
    context_sha256: str
    schema_sha256: str
    selected_prompt_keys: tuple[str, ...]
    selected_family_keys: tuple[str, ...]
    selected_focus_key: str | None
    selected_strategy_key: str | None
    estimated_tokens: int
    bundle_sha256: str


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def prompt_asset_payload(
    asset: PromptAsset, *, include_content: bool = True
) -> dict[str, Any]:
    payload = {
        "prompt_key": asset.prompt_key,
        "prompt_role": asset.prompt_role,
        "language": asset.language,
        "content_sha256": asset.content_sha256,
        "family_key": asset.family_key,
        "report_domain_keys": list(asset.report_domain_keys),
        "focus_key": asset.focus_key,
        "strategy_key": asset.strategy_key,
        "species": asset.species,
        "input_scope": asset.input_scope,
        "output_contract": asset.output_contract,
        "eligibility": asset.eligibility,
        "status": asset.status,
    }
    if include_content:
        payload["content"] = asset.content
    return payload


def schema_asset_payload(schema: SchemaAsset) -> dict[str, Any]:
    return {
        "schema_key": schema.schema_key,
        "schema_version": schema.schema_version,
        "language": schema.language,
        "schema": schema.schema,
        "schema_sha256": schema.schema_sha256,
        "output_contract": schema.output_contract,
        "status": schema.status,
    }


__all__ = [
    "CompiledPrompt",
    "PRIMARY_FAMILY_ORDER",
    "PROMPT_LANGUAGE",
    "PROMPT_ROLES",
    "PromptAsset",
    "PromptBundle",
    "PromptContractError",
    "SchemaAsset",
    "canonical_json",
    "prompt_asset_payload",
    "schema_asset_payload",
    "sha256_json",
    "sha256_text",
]
