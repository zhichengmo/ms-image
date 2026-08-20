"""Filesystem source catalog compiled into immutable AI Config prompt bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import (
    PROMPT_LANGUAGE,
    PromptAsset,
    PromptBundle,
    PromptContractError,
    SchemaAsset,
    sha256_json,
)


class PromptCatalog:
    def __init__(self, *, root: Path, catalog_revision: str):
        self.root = root
        self.catalog_revision = catalog_revision
        self._assets, self._schema = self._load()

    @classmethod
    def target_xray(cls, catalog_revision: str) -> "PromptCatalog":
        root = Path(__file__).resolve().parents[4] / "prompts" / "xray"
        return cls(root=root, catalog_revision=catalog_revision)

    @property
    def schema(self) -> SchemaAsset:
        return self._schema

    def asset(
        self,
        *,
        prompt_role: str,
        prompt_key: str | None = None,
        family_key: str | None = None,
        focus_key: str | None = None,
        strategy_key: str | None = None,
        eligibility: str | None = None,
    ) -> PromptAsset:
        candidates = [
            item
            for item in self._assets
            if item.prompt_role == prompt_role
            and (prompt_key is None or item.prompt_key == prompt_key)
            and (family_key is None or item.family_key == family_key)
            and (focus_key is None or item.focus_key == focus_key)
            and (strategy_key is None or item.strategy_key == strategy_key)
            and (eligibility is None or item.eligibility == eligibility)
        ]
        if len(candidates) != 1:
            raise PromptContractError("prompt_asset_selection_ambiguous")
        return candidates[0]

    def assets_for_role(self, prompt_role: str) -> tuple[PromptAsset, ...]:
        return tuple(item for item in self._assets if item.prompt_role == prompt_role)

    def build_bundle(self) -> PromptBundle:
        primary = tuple(
            item
            for item in self._assets
            if item.prompt_role
            in {"joint_primary_base", "joint_primary_module", "technical_evidence"}
        )
        targeted = tuple(
            item
            for item in self._assets
            if item.prompt_role
            in {"targeted_focus", "review_strategy", "technical_evidence"}
        )
        offline = tuple(
            item for item in self._assets if item.prompt_role == "offline_evaluation"
        )
        bundle_payload = {
            "bundle_version": "xray-prompt-bundle.v1",
            "catalog_revision": self.catalog_revision,
            "language": PROMPT_LANGUAGE,
            "assets": [
                {
                    "prompt_key": item.prompt_key,
                    "prompt_role": item.prompt_role,
                    "content_sha256": item.content_sha256,
                    "family_key": item.family_key,
                    "focus_key": item.focus_key,
                    "strategy_key": item.strategy_key,
                    "eligibility": item.eligibility,
                }
                for item in self._assets
            ],
            "schema": {
                "schema_key": self.schema.schema_key,
                "schema_version": self.schema.schema_version,
                "schema_sha256": self.schema.schema_sha256,
            },
        }
        return PromptBundle(
            bundle_version="xray-prompt-bundle.v1",
            catalog_revision=self.catalog_revision,
            language=PROMPT_LANGUAGE,
            primary_assets=primary,
            targeted_assets=targeted,
            offline_assets=offline,
            schema=self.schema,
            bundle_sha256=sha256_json(bundle_payload),
        )

    def _load(self) -> tuple[tuple[PromptAsset, ...], SchemaAsset]:
        manifest_path = self.root / "catalog.zh-CN.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PromptContractError("prompt_catalog_invalid") from exc
        if manifest.get("catalog_revision") != self.catalog_revision:
            raise PromptContractError("prompt_catalog_revision_not_available")
        if manifest.get("language") != PROMPT_LANGUAGE:
            raise PromptContractError("prompt_language_not_available")
        assets: list[PromptAsset] = []
        seen_keys: set[str] = set()
        for item in manifest.get("assets", []):
            prompt_key = str(item.get("prompt_key") or "")
            if prompt_key in seen_keys:
                raise PromptContractError("prompt_key_duplicate")
            seen_keys.add(prompt_key)
            filename = item.get("filename")
            if not isinstance(filename, str):
                raise PromptContractError("prompt_asset_filename_invalid")
            try:
                content = (self.root / filename).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise PromptContractError("prompt_asset_not_found") from exc
            assets.append(
                PromptAsset(
                    prompt_key=prompt_key,
                    prompt_role=str(item.get("prompt_role") or ""),
                    language=str(item.get("language") or ""),
                    content=content,
                    content_sha256=str(item.get("content_sha256") or ""),
                    family_key=item.get("family_key"),
                    report_domain_keys=tuple(item.get("report_domain_keys") or ()),
                    focus_key=item.get("focus_key"),
                    strategy_key=item.get("strategy_key"),
                    species=str(item.get("species") or "all"),
                    input_scope=str(item.get("input_scope") or ""),
                    output_contract=str(item.get("output_contract") or ""),
                    eligibility=str(item.get("eligibility") or ""),
                    status=str(item.get("status") or ""),
                )
            )
        schema_item: dict[str, Any] = manifest.get("schema") or {}
        schema_filename = schema_item.get("filename")
        if not isinstance(schema_filename, str):
            raise PromptContractError("schema_asset_filename_invalid")
        try:
            schema = json.loads(
                (self.root / schema_filename).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise PromptContractError("schema_asset_not_found") from exc
        schema_asset = SchemaAsset(
            schema_key=str(schema_item.get("schema_key") or ""),
            schema_version=str(schema_item.get("schema_version") or ""),
            language=str(schema_item.get("language") or ""),
            schema=schema,
            schema_sha256=str(schema_item.get("schema_sha256") or ""),
            output_contract=str(schema_item.get("output_contract") or ""),
            status=str(schema_item.get("status") or ""),
        )
        if not assets:
            raise PromptContractError("prompt_catalog_empty")
        return tuple(assets), schema_asset


__all__ = ["PromptCatalog"]
