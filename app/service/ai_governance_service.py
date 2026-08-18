"""Runtime resolution of the legacy vet-platform AI configuration contract.

The old service does not select a provider from environment variables.  It
resolves ``ai_config.items`` in order, treats the last item as an
``ai_model_pool`` id, loads prompt/config items, and then expands the ordered
``ai_api_connection`` ids in that pool.  This module keeps that contract while
using ms-image's ``DalBase`` based DALs and OpenAI-compatible transport.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai_runtime import (
    AiApiConnectionDal,
    AiConfigDal,
    AiModelPoolDal,
    AiPromptTemplateDal,
    GptConfigItemDal,
)


@dataclass(frozen=True)
class PromptTemplateConfig:
    item_id: str
    content: str
    name: str | None
    weight: float = 1.0


@dataclass(frozen=True)
class ModelProfile:
    item_id: str
    name: str
    note: str | None
    weight: float = 1.0


@dataclass(frozen=True)
class OutputFormat:
    item_id: str
    value: str
    note: str | None


@dataclass(frozen=True)
class ParameterEntry:
    item_id: str
    raw: str
    parsed: object | None


@dataclass(frozen=True)
class GovernedConnection:
    """One ordered legacy ``ai_api_connection`` entry.

    The legacy table has no timeout/max-token columns.  Those values are
    runtime policy defaults, never provider-selection configuration.  The
    endpoint, model, credential and pool order all come from the legacy DB.
    """

    connection_id: str
    base_url: str
    model: str
    api_key: str
    secret_ref: str
    timeout_seconds: float = 30.0
    max_tokens: int = 2048
    cooldown_seconds: float = 30.0


@dataclass(frozen=True)
class AIConfigBundle:
    version: str
    raw_item_ids: tuple[str, ...]
    connection_pool_id: str
    prompt_templates: tuple[PromptTemplateConfig, ...] = ()
    model_profiles: tuple[ModelProfile, ...] = ()
    output_configs: tuple[OutputFormat, ...] = ()
    params: tuple[ParameterEntry, ...] = ()
    connection_pool: tuple[str, ...] = ()
    connection_entries: tuple[GovernedConnection, ...] = ()
    timeout_seconds: float = 30.0
    max_tokens: int = 2048

    @property
    def prompt(self) -> PromptTemplateConfig:
        if not self.prompt_templates:
            raise ValueError("ai_prompt_template_not_found")
        return self.prompt_templates[0]

    def as_legacy_dict(self) -> dict[str, list[object] | object | None]:
        """Expose the same flattened shape consumed by vet-platform callers."""
        return {
            "prompt": [item.content for item in self.prompt_templates],
            "model_version": [item.name for item in self.model_profiles],
            "output_format": [item.value for item in self.output_configs],
            "param": [item.raw for item in self.params],
            "connection_pool": list(self.connection_pool),
            "connection_entry_ids": [item.connection_id for item in self.connection_entries],
            "prompt_template_id": self.prompt.item_id if self.prompt_templates else None,
            "connection_pool_id": self.connection_pool_id,
            "version": self.version,
        }

    @staticmethod
    def _param_value(params: tuple[ParameterEntry, ...], names: set[str]) -> object | None:
        for entry in params:
            value = entry.parsed
            if not isinstance(value, dict):
                continue
            for key, candidate in value.items():
                if str(key).casefold() in names:
                    return candidate
        return None


class AIGovernanceService:
    """Resolve the old DB-backed AI chain; no XRAY_PROVIDER env access."""

    def __init__(self, db: AsyncSession):
        self.config_dal = AiConfigDal(db)
        self.pool_dal = AiModelPoolDal(db)
        self.connection_dal = AiApiConnectionDal(db)
        self.prompt_dal = AiPromptTemplateDal(db)
        self.item_dal = GptConfigItemDal(db)

    @staticmethod
    def _split_ids(value: str | None) -> list[str]:
        return [part.strip() for part in (value or "").split("-") if part.strip()]

    async def resolve(self, *, version: str, language: str = "en") -> AIConfigBundle:
        config = await self.config_dal.get_active_by_version(version)
        if config is None or not config.items:
            raise ValueError("ai_config_not_found")
        raw_ids = self._split_ids(config.items)
        if len(raw_ids) < 2:
            raise ValueError("ai_config_pool_missing")
        pool_id = raw_ids[-1]
        item_ids = raw_ids[:-1]

        prompts = await self.prompt_dal.list_active_by_ids(item_ids)
        prompt_map = {str(item.id): item for item in prompts}
        config_items = await self.item_dal.list_active_by_ids(item_ids)
        item_map = {str(item.id): item for item in config_items}

        prompt_values: list[PromptTemplateConfig] = []
        model_values: list[ModelProfile] = []
        output_values: list[OutputFormat] = []
        param_values: list[ParameterEntry] = []
        for item_id in item_ids:
            # This precedence is intentional and matches vet-platform when an
            # id happens to exist in both legacy tables.
            prompt = prompt_map.get(item_id)
            if prompt is not None:
                content = prompt.content_en if language.casefold() == "en" and prompt.content_en else prompt.content
                prompt_values.append(
                    PromptTemplateConfig(
                        item_id=item_id,
                        content=content or "",
                        name=prompt.template_name,
                        weight=float(prompt.human_weight or 1.0),
                    )
                )
                continue
            item = item_map.get(item_id)
            if item is None:
                continue
            config_type = str(item.config_type or "")
            if config_type == "2":
                model_values.append(ModelProfile(item_id, (item.content or "").strip(), item.note, float(item.human_weight or 1.0)))
            elif config_type == "3":
                output_values.append(OutputFormat(item_id, (item.content or "").strip(), item.note))
            elif config_type == "5":
                raw = item.content or ""
                try:
                    parsed = json.loads(raw) if raw else None
                except (TypeError, ValueError, json.JSONDecodeError):
                    parsed = None
                param_values.append(ParameterEntry(item_id, raw, parsed))

        connections = await self.resolve_pool(pool_id=pool_id)
        if not prompt_values:
            raise ValueError("ai_prompt_template_not_found")
        timeout_value = AIConfigBundle._param_value(
            tuple(param_values), {"timeout", "timeout_seconds", "request_timeout_seconds"}
        )
        max_tokens_value = AIConfigBundle._param_value(
            tuple(param_values), {"max_tokens", "max_output_tokens", "max_completion_tokens"}
        )
        try:
            timeout_seconds = max(1.0, float(timeout_value)) if timeout_value is not None else 30.0
        except (TypeError, ValueError):
            timeout_seconds = 30.0
        try:
            max_tokens = max(1, int(max_tokens_value)) if max_tokens_value is not None else 2048
        except (TypeError, ValueError):
            max_tokens = 2048
        connections = tuple(
            replace(entry, timeout_seconds=timeout_seconds, max_tokens=max_tokens)
            for entry in connections
        )
        return AIConfigBundle(
            version=version,
            raw_item_ids=tuple(item_ids),
            connection_pool_id=pool_id,
            prompt_templates=tuple(prompt_values),
            model_profiles=tuple(model_values),
            output_configs=tuple(output_values),
            params=tuple(param_values),
            connection_pool=tuple(
                f"{entry.base_url}|{entry.api_key}|{entry.model}" for entry in connections
            ),
            connection_entries=connections,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )

    async def get_config(
        self,
        *,
        version: str,
        language: str = "en",
        as_dict: bool = True,
    ) -> AIConfigBundle | dict[str, list[object] | object | None]:
        """Compatibility entry point matching old ``AiConfigService``."""
        bundle = await self.resolve(version=version, language=language)
        return bundle.as_legacy_dict() if as_dict else bundle

    async def resolve_config(self, *, version: str, language: str = "en") -> tuple[str, PromptTemplateConfig]:
        """Compatibility projection for callers that only need pool + prompt."""
        bundle = await self.resolve(version=version, language=language)
        return bundle.connection_pool_id, bundle.prompt

    async def resolve_pool(self, *, pool_id: str) -> tuple[GovernedConnection, ...]:
        pool = await self.pool_dal.get_by_id(pool_id)
        if pool is None or not pool.model_pool:
            raise ValueError("ai_model_pool_not_found")
        connection_ids = self._split_ids(pool.model_pool)
        rows = await self.connection_dal.list_active_by_ids(connection_ids)
        if len(rows) != len(connection_ids):
            raise ValueError("ai_model_pool_connection_not_found")
        by_id = {str(row.id): row for row in rows}
        result: list[GovernedConnection] = []
        for connection_id in connection_ids:
            row = by_id[connection_id]
            base_url = (row.base_url or "").strip()
            model = (row.model_name or "").strip()
            api_key = (row.api_key or "").strip()
            if not base_url or not model or not api_key:
                raise ValueError("ai_connection_secret_unavailable")
            result.append(
                GovernedConnection(
                    connection_id=connection_id,
                    base_url=base_url,
                    model=model,
                    api_key=api_key,
                    secret_ref=f"ai_api_connection:{connection_id}",
                )
            )
        return tuple(result)


__all__ = [
    "AIGovernanceService",
    "AIConfigBundle",
    "GovernedConnection",
    "PromptTemplateConfig",
    "ModelProfile",
    "OutputFormat",
    "ParameterEntry",
]
