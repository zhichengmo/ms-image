"""Versioned, leakage-checked Prompt assets for the validation-only chain."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from time import monotonic
from typing import Any, Callable


PROMPT_ROOT = Path(__file__).resolve().parents[3] / "prompts" / "xray_accuracy"
SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas" / "xray_accuracy"
FORBIDDEN_PROMPT_TOKENS = frozenset({"abn", "nor", "disease_code", "filename", "path", "history", "truth", "annotation", "ocr", "exif", "failure_bank", "score", "diagnosis", "previous_output", "signed_url", "original_image"})


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _find_forbidden(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in FORBIDDEN_PROMPT_TOKENS:
                hits.append(f"{path}.{key_text}")
            hits.extend(_find_forbidden(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_find_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(token in lowered for token in FORBIDDEN_PROMPT_TOKENS):
            hits.append(path)
    return hits


@dataclass(frozen=True)
class PromptRevision:
    prompt_key: str
    node_key: str
    language: str
    version: str
    filename: str
    schema_key: str
    status: str = "draft"
    active: bool = False
    variables: tuple[str, ...] = ()
    checksum: str | None = None
    module_key: str = "xray_accuracy"


@dataclass(frozen=True)
class PromptManifest:
    prompt_key: str
    node_key: str
    language: str
    version: str
    template_path: str
    schema_key: str
    body: str
    status: str
    variables: tuple[str, ...]
    checksum: str
    species_scope: str = "all"
    body_scope: str = "technical_request_gate"
    owner: str = "xray-platform"
    active: str = "yes"
    validated_at: str = "2026-08-09"
    commit: str = "working-tree"
    module_key: str = "xray_accuracy"

    @property
    def variables_json(self) -> list[str]:
        return list(self.variables)

    @property
    def prompt_sha256(self) -> str:
        return sha256_text(self.body)


@dataclass(frozen=True)
class RenderedPrompt:
    manifest: PromptManifest
    rendered_body: str
    rendered_sha256: str
    context_sha256: str


class XRayPromptRegistry:
    """Filesystem-backed registry; runtime reads published + active only."""

    _CONTEXT_FIELDS = ("attempt_id", "image_count", "node_key", "release_fingerprint", "run_id", "trace_namespace")
    _ASSETS = (
        PromptRevision(
            prompt_key="xray.request_gate.v1",
            node_key="request_gate",
            language="en",
            version="v1",
            filename="request_gate.v1.txt",
            schema_key="xray.request-gate-response.v1",
            status="published",
            active=True,
            variables=_CONTEXT_FIELDS,
            checksum="13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f",
        ),
    )

    def __init__(self, *, revisions: tuple[PromptRevision, ...] | None = None, cache_ttl_seconds: float = 120.0, clock: Callable[[], float] = monotonic):
        self.revisions = revisions or self._ASSETS
        self.cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self.clock = clock
        self._cache: dict[tuple[str, str, str | None, str], tuple[float, PromptManifest]] = {}

    def _select_revision(self, prompt_key: str, version: str | None, language: str, module_key: str) -> PromptRevision:
        candidates = [revision for revision in self.revisions if revision.module_key == module_key and revision.prompt_key == prompt_key and revision.status == "published" and revision.active and (version is None or revision.version == version)]
        if not candidates:
            raise ValueError("prompt_published_active_revision_not_found")
        # A missing language is a hard contract failure.  Silent fallback to a
        # different Prompt language makes paired runs non-comparable and can
        # hide an accidental bilingual configuration drift.
        matched = [revision for revision in candidates if revision.language.casefold() == language.casefold()]
        if matched:
            latest_version = sorted({item.version for item in matched})[-1]
            latest = [item for item in matched if item.version == latest_version]
            if len(latest) != 1:
                raise ValueError("prompt_revision_ambiguous")
            return latest[0]
        raise ValueError("prompt_language_not_available")

    def get_manifest(self, prompt_key: str = "xray.request_gate.v1", *, module_key: str = "xray_accuracy", version: str | None = None, language: str = "en", force_refresh: bool = False) -> PromptManifest:
        cache_key = (module_key, prompt_key, version, language)
        cached = self._cache.get(cache_key)
        now = self.clock()
        if not force_refresh and cached is not None and cached[0] > now:
            return cached[1]
        revision = self._select_revision(prompt_key, version, language, module_key)
        path = PROMPT_ROOT / revision.filename
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            raise ValueError("prompt_empty")
        checksum = sha256_text(body)
        if revision.checksum is None:
            raise ValueError("prompt_checksum_missing")
        if revision.checksum != checksum:
            raise ValueError("prompt_checksum_mismatch")
        manifest = PromptManifest(prompt_key=prompt_key, node_key=revision.node_key, language=revision.language, version=revision.version, template_path=str(path), schema_key=revision.schema_key, body=body, status=revision.status, variables=revision.variables, checksum=checksum, active="yes", module_key=module_key)
        self._cache[cache_key] = (now + self.cache_ttl_seconds, manifest)
        return manifest

    def render(self, *, prompt_key: str, context: dict[str, Any], module_key: str = "xray_accuracy", version: str | None = None, language: str = "en", force_refresh: bool = False) -> RenderedPrompt:
        manifest = self.get_manifest(prompt_key, module_key=module_key, version=version, language=language, force_refresh=force_refresh)
        if set(context) != set(manifest.variables):
            raise ValueError("prompt_context_fields_invalid")
        if _find_forbidden(context):
            raise ValueError("prompt_context_leakage_invalid")
        context_json = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        rendered = f"{manifest.body}\n\nTECHNICAL_CONTEXT_JSON={context_json}"
        if _find_forbidden(rendered, "$.rendered_body"):
            raise ValueError("prompt_rendered_leakage_invalid")
        return RenderedPrompt(manifest=manifest, rendered_body=rendered, rendered_sha256=sha256_text(rendered), context_sha256=sha256_text(context_json))

    def response_schema(self, schema_key: str) -> tuple[dict[str, Any], str]:
        if schema_key != "xray.request-gate-response.v1":
            raise ValueError("response_schema_not_registered")
        path = SCHEMA_ROOT / "request_gate_response.v1.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return schema, sha256_text(canonical)
