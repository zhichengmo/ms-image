"""Code-owned AI model routes, aligned with ms-ai-fast."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AiModelRoute:
    """定义单个业务接口使用的候选模型列表和调度模式。"""

    models: tuple[str, ...]
    mode: Literal["round_robin", "race"] = "race"

    def __post_init__(self) -> None:
        if self.mode not in {"round_robin", "race"}:
            raise ValueError("mode 仅支持 round_robin 或 race")
        normalized = tuple(dict.fromkeys(model.strip() for model in self.models))
        if not normalized or any(not model for model in normalized):
            raise ValueError("models 必须包含至少一个非空模型")
        object.__setattr__(self, "models", normalized)


__all__ = ["AiModelRoute"]
