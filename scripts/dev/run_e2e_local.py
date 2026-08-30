#!/usr/bin/env python3
"""Run repeatable local XRay engineering E2E checks via the public Runtime API.

This tool verifies public Image, Study, Task and Report contracts. It does not
query the database, infer medical facts, or print credentials, signed URLs,
clinical text, Provider responses or report content.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


DEFAULT_API_BASE = "http://127.0.0.1:8010/api/v1"
DEFAULT_DEV_PYTHON = "/opt/homebrew/anaconda3/bin/python3.12"
CLINICAL_CONTEXT_VERSION = "xray-clinical-context.v1"
SNAPSHOT_VERSION = "task-request-snapshot.v3"
SERIES_MANIFEST_VERSION = "series-image-manifest.v2"
PROJECTION_SCHEMA_VERSION = "xray-projection.v1"
PROJECTION_SOURCE = "caller_declared"
COMPLETE_RESULT_VERSION = "xray-complete-medical-result.v2"
CASE_MANIFEST_VERSION = "xray-e2e-case.v1"
DATA_ROOT_ENV = "MS_IMAGE_XRAY_DATA_ROOT"
TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled", "dead_letter"}


class E2EError(RuntimeError):
    """A sanitized engineering acceptance failure."""


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def non_empty_projection(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("must not be empty")
    if len(normalized) > 64:
        raise argparse.ArgumentTypeError("must be at most 64 characters")
    return normalized


def optional_non_empty(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("must not be empty")
    return normalized


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_recorded_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be an ISO-8601 datetime with a timezone"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("must include a timezone")
    return utc_iso(parsed)


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


def require_sha256(value: Any, message: str) -> str:
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        message,
    )
    return value


def sha256_argument(value: str) -> str:
    normalized = value.strip().lower()
    if (
        len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise argparse.ArgumentTypeError("must be a lowercase SHA256 value")
    return normalized


def image_media_type(path: Path) -> tuple[str, str]:
    formats = {
        ".dcm": ("dicom", "application/dicom"),
        ".dicom": ("dicom", "application/dicom"),
        ".jpg": ("jpeg", "image/jpeg"),
        ".jpeg": ("jpeg", "image/jpeg"),
        ".png": ("png", "image/png"),
    }
    try:
        return formats[path.suffix.casefold()]
    except KeyError as exc:
        raise E2EError("image extension is not supported by the upload contract") from exc


def _read_image_fact(*, data_root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "path",
        "sha256",
        "size_bytes",
        "file_format",
        "content_type",
        "sequence_no",
        "projection",
    }
    require(set(raw) == allowed, "case manifest image fields are invalid")
    relative = raw.get("path")
    require(isinstance(relative, str) and bool(relative.strip()), "image path is invalid")
    relative_path = Path(relative)
    require(
        not relative_path.is_absolute() and ".." not in relative_path.parts,
        "image path must be relative to the configured data root",
    )
    path = (data_root / relative_path).resolve()
    require(path.is_relative_to(data_root), "image path escaped the configured data root")
    require(path.is_file(), "case manifest image file is missing")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise E2EError("case manifest image file could not be read") from exc
    require(bool(content), "case manifest image file is empty")
    actual_sha256 = hashlib.sha256(content).hexdigest()
    require(raw.get("sha256") == actual_sha256, "case manifest image SHA256 drifted")
    require(raw.get("size_bytes") == len(content), "case manifest image size drifted")
    file_format, content_type = image_media_type(path)
    require(raw.get("file_format") == file_format, "case manifest image format drifted")
    require(
        raw.get("content_type") == content_type,
        "case manifest image content type drifted",
    )
    sequence_no = raw.get("sequence_no")
    require(
        isinstance(sequence_no, int)
        and not isinstance(sequence_no, bool)
        and sequence_no >= 1,
        "case manifest image sequence number is invalid",
    )
    projection = raw.get("projection")
    require(
        isinstance(projection, str)
        and projection == projection.strip()
        and 1 <= len(projection) <= 64,
        "case manifest image projection is invalid",
    )
    return {
        **raw,
        "path": path,
        "content": content,
    }


def load_case_manifest(path: Path) -> dict[str, Any]:
    data_root_raw = os.environ.get(DATA_ROOT_ENV, "").strip()
    require(bool(data_root_raw), f"{DATA_ROOT_ENV} is required for case manifest mode")
    data_root = Path(data_root_raw).expanduser().resolve()
    require(data_root.is_dir(), f"{DATA_ROOT_ENV} must point to an existing directory")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise E2EError("case manifest could not be read as JSON") from exc
    require(isinstance(raw, dict), "case manifest root is invalid")
    allowed = {
        "contract_version",
        "case_key",
        "grouping_status",
        "grouping_method",
        "source_group_fingerprint_sha256",
        "species",
        "modality_type",
        "body_part",
        "series",
    }
    require(set(raw).issubset(allowed), "case manifest root fields are invalid")
    require(raw.get("contract_version") == CASE_MANIFEST_VERSION, "case manifest version is invalid")
    require(raw.get("grouping_status") == "engineering_candidate", "case grouping status is invalid")
    require(raw.get("species") in {"cat", "dog"}, "case manifest species is invalid")
    require(raw.get("modality_type") == "xray", "case manifest modality is invalid")
    require(
        isinstance(raw.get("case_key"), str) and bool(raw["case_key"].strip()),
        "case key is invalid",
    )
    require(
        isinstance(raw.get("grouping_method"), str)
        and bool(raw["grouping_method"].strip()),
        "case grouping method is invalid",
    )
    require_sha256(
        raw.get("source_group_fingerprint_sha256"),
        "case grouping fingerprint is invalid",
    )
    if "body_part" in raw:
        require(
            isinstance(raw["body_part"], str) and bool(raw["body_part"].strip()),
            "case body part is invalid",
        )
    raw_series = raw.get("series")
    require(isinstance(raw_series, list) and raw_series, "case manifest series are invalid")
    series_rows: list[dict[str, Any]] = []
    sequence_numbers: list[int] = []
    series_keys: set[str] = set()
    for index, item in enumerate(raw_series, 1):
        require(isinstance(item, dict), "case manifest series item is invalid")
        require(set(item) == {"series_key", "images"}, "case manifest series fields are invalid")
        series_key = item.get("series_key")
        require(
            isinstance(series_key, str)
            and bool(series_key.strip())
            and series_key not in series_keys,
            "case manifest series key is invalid",
        )
        series_keys.add(series_key)
        images_raw = item.get("images")
        require(
            isinstance(images_raw, list) and 1 <= len(images_raw) <= 5,
            "case manifest series image count is out of range",
        )
        images = [
            _read_image_fact(data_root=data_root, raw=image)
            for image in images_raw
            if isinstance(image, dict)
        ]
        require(len(images) == len(images_raw), "case manifest image item is invalid")
        sequence_numbers.extend(image["sequence_no"] for image in images)
        series_rows.append(
            {"series_key": series_key, "series_no": index, "images": images}
        )
    total_images = sum(len(item["images"]) for item in series_rows)
    require(2 <= total_images <= 5, "case manifest Study image count is out of range")
    require(
        sorted(sequence_numbers) == list(range(1, total_images + 1)),
        "case manifest sequence numbers must be unique and continuous",
    )
    return {
        **raw,
        "series": series_rows,
        "image_count": total_images,
        "manifest_sha256": canonical_sha256(raw),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the public ms-image XRay engineering E2E one or more times."
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--case-manifest", type=Path)
    parser.add_argument("--species", choices=("cat", "dog"))
    parser.add_argument("--projection", type=non_empty_projection)
    parser.add_argument("--body-part", type=optional_non_empty)
    parser.add_argument(
        "--clinical-context-mode",
        choices=("synthetic", "none"),
        default="synthetic",
    )
    parser.add_argument("--context-recorded-at", type=parse_recorded_at)
    parser.add_argument("--repeat", type=positive_int, default=1)
    parser.add_argument("--expected-config-key", type=optional_non_empty)
    parser.add_argument("--expected-prompt-sha256", type=sha256_argument)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--verify-runtime-receipt", action="store_true")
    args = parser.parse_args(argv)

    args.api_base = args.api_base.strip().rstrip("/")
    if not args.api_base:
        parser.error("--api-base must not be empty")
    if args.case_manifest is not None:
        args.case_manifest = args.case_manifest.expanduser().resolve()
        if not args.case_manifest.is_file():
            parser.error("--case-manifest must point to an existing JSON file")
        if any(
            value is not None
            for value in (args.image, args.species, args.projection, args.body_part)
        ):
            parser.error(
                "--case-manifest cannot be combined with --image, --species, "
                "--projection or --body-part"
            )
    else:
        if args.species is None:
            parser.error("--species is required with --image")
        args.projection = args.projection or "UNKNOWN"
        args.image = args.image.expanduser().resolve()
        if not args.image.is_file():
            parser.error("--image must point to an existing file")
        try:
            image_media_type(args.image)
        except E2EError as exc:
            parser.error(str(exc))
    if args.verify_runtime_receipt and args.case_manifest is None:
        parser.error("--verify-runtime-receipt requires --case-manifest")
    if args.verify_runtime_receipt and args.expected_config_key is None:
        parser.error(
            "--verify-runtime-receipt requires --expected-config-key and "
            "--expected-prompt-sha256"
        )
    if args.verify_runtime_receipt and args.evidence_dir is None:
        parser.error("--verify-runtime-receipt requires --evidence-dir")
    if args.evidence_dir is not None:
        args.evidence_dir = args.evidence_dir.expanduser().resolve()
    if args.clinical_context_mode == "none" and args.context_recorded_at is not None:
        parser.error("--context-recorded-at requires synthetic context mode")
    if (args.expected_config_key is None) != (
        args.expected_prompt_sha256 is None
    ):
        parser.error(
            "--expected-config-key and --expected-prompt-sha256 must be supplied together"
        )
    return args


def issue_dev_token() -> str:
    script = Path(__file__).resolve().parent / "issue_dev_token.py"
    python = Path(os.environ.get("MS_IMAGE_LOCAL_PYTHON", DEFAULT_DEV_PYTHON))
    require(python.is_file(), "local-chain Python executable is missing")
    try:
        result = subprocess.run(
            [str(python), str(script)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise E2EError("development token issuance failed") from exc
    token = result.stdout.strip()
    require(bool(token), "development token issuance returned an empty token")
    return token


class RuntimeClient:
    def __init__(self, *, api_base: str, token: str) -> None:
        self.api_base = api_base
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    def close(self) -> None:
        self.client.close()

    def call(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        expected: tuple[int, ...] = (200, 201),
    ) -> Any:
        try:
            response = self.client.request(
                method,
                self.api_base + endpoint,
                json=payload,
                params=params,
            )
        except httpx.RequestError as exc:
            raise E2EError(f"{method} {endpoint} transport failed") from exc
        if response.status_code not in expected:
            raise E2EError(
                f"{method} {endpoint} returned HTTP {response.status_code}"
            )
        try:
            envelope = response.json()
        except ValueError as exc:
            raise E2EError(f"{method} {endpoint} returned invalid JSON") from exc
        require(isinstance(envelope, dict), f"{method} {endpoint} envelope is invalid")
        require(envelope.get("success") is True, f"{method} {endpoint} was unsuccessful")
        require("data" in envelope, f"{method} {endpoint} omitted data")
        return envelope["data"]


def build_clinical_context(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.clinical_context_mode == "none":
        return None
    recorded_at = args.context_recorded_at or utc_iso(datetime.now(timezone.utc))
    return {
        "contract_version": CLINICAL_CONTEXT_VERSION,
        "source": {
            "system": "ms-image-local-e2e",
            "recorded_at": recorded_at,
            "temporal_scope": "available_at_request",
        },
        "chief_complaint": "合成工程上下文，不代表真实临床主诉",
        "study_reason": "合成工程上下文，仅验证冻结和传递",
    }


def wait_for_image(client: RuntimeClient, image_id: str) -> dict[str, Any]:
    for _ in range(30):
        image = client.call("GET", "/images", params={"id": image_id})
        require(isinstance(image, dict), "Image response is invalid")
        status = image.get("status")
        if status == "ready":
            return image
        if status not in {"uploading", "validating"}:
            raise E2EError(f"Image entered terminal status {status}")
        time.sleep(2)
    raise E2EError("Image did not become ready before the polling deadline")


def wait_for_task(client: RuntimeClient, task_id: str) -> dict[str, Any]:
    for _ in range(120):
        task = client.call("GET", "/tasks", params={"id": task_id})
        require(isinstance(task, dict), "Task response is invalid")
        status = task.get("execution_status")
        if status in TERMINAL_TASK_STATUSES:
            require(status == "completed", f"Task entered terminal status {status}")
            return task
        time.sleep(3)
    raise E2EError("Task did not complete before the polling deadline")


def validate_image(
    image: dict[str, Any],
    *,
    image_id: str,
    series_id: str,
    projection: str,
    image_sha256: str,
    image_size: int,
    content_type: str,
) -> None:
    require(image.get("id") == image_id, "Image ID drifted")
    require(image.get("series_id") == series_id, "Image series ID drifted")
    require(image.get("status") == "ready", "Image is not ready")
    require(image.get("sha256") == image_sha256, "Image SHA256 drifted")
    require(image.get("size_bytes") == image_size, "Image size drifted")
    require(image.get("content_type") == content_type, "Image content type drifted")
    require(image.get("projection") == projection, "Image projection drifted")
    require(
        image.get("projection_provenance")
        == {
            "source": PROJECTION_SOURCE,
            "schema_version": PROJECTION_SCHEMA_VERSION,
        },
        "Image projection provenance is incomplete",
    )


def validate_snapshot(
    task: dict[str, Any],
    *,
    study: dict[str, Any],
    series: list[dict[str, Any]],
    images: list[dict[str, Any]],
    clinical_context: dict[str, Any] | None,
    species: str,
    expected_config_key: str | None,
    expected_prompt_sha256: str | None,
) -> dict[str, Any]:
    snapshot = task.get("request_snapshot_json")
    require(isinstance(snapshot, dict), "Task Snapshot is missing")
    require(
        snapshot.get("snapshot_contract_version") == SNAPSHOT_VERSION,
        "Task Snapshot is not v3",
    )
    require(
        snapshot.get("resolved_manifest_sha256") == study.get("resolved_manifest_sha256"),
        "Study manifest SHA drifted in Task Snapshot",
    )
    require(snapshot.get("species") == species, "Task Snapshot species drifted")
    if expected_config_key is not None:
        require(
            snapshot.get("config_key") == expected_config_key,
            "Task Snapshot Config key did not match the qualified species route",
        )
        require(
            snapshot.get("prompt_content_sha256") == expected_prompt_sha256,
            "Task Snapshot Prompt SHA256 did not match the qualified release",
        )

    expected_context = clinical_context or {}
    expected_context_sha = canonical_sha256(expected_context)
    require(
        snapshot.get("clinical_context_policy_version") == CLINICAL_CONTEXT_VERSION,
        "clinical context policy version drifted",
    )
    require(
        snapshot.get("clinical_context_allowlist") == expected_context,
        "clinical context allowlist drifted",
    )
    require(
        snapshot.get("clinical_context_sha256") == expected_context_sha,
        "clinical context SHA256 drifted",
    )

    frozen_series = snapshot.get("series")
    require(
        isinstance(frozen_series, list) and len(frozen_series) == len(series),
        "D1 series snapshot is invalid",
    )
    series_by_id = {item.get("id"): item for item in series}
    require(len(series_by_id) == len(series), "Runtime Series IDs are invalid")
    images_by_series: dict[str, list[dict[str, Any]]] = {
        str(series_id): [] for series_id in series_by_id
    }
    for image in images:
        series_id = image.get("series_id")
        require(series_id in images_by_series, "Runtime Image escaped its Study Series")
        images_by_series[series_id].append(image)

    study_manifest_items: list[dict[str, Any]] = []
    series_manifest_sha256: dict[str, str] = {}
    frozen_series_ids: set[str] = set()
    for frozen in frozen_series:
        require(isinstance(frozen, dict), "D1 series snapshot item is invalid")
        series_id = frozen.get("series_id")
        runtime_series = series_by_id.get(series_id)
        require(runtime_series is not None, "D1 series ID drifted")
        require(series_id not in frozen_series_ids, "D1 series ID is duplicated")
        frozen_series_ids.add(series_id)
        require(
            frozen.get("series_key") == runtime_series.get("series_key"),
            "D1 series key drifted",
        )
        require(
            frozen.get("series_no") == runtime_series.get("series_no"),
            "D1 series number drifted",
        )
        require(
            frozen.get("manifest_contract_version") == SERIES_MANIFEST_VERSION,
            "D1 series manifest version drifted",
        )
        runtime_images = sorted(
            images_by_series[series_id], key=lambda item: item["sequence_no"]
        )
        require(
            frozen.get("actual_image_count") == len(runtime_images),
            "D1 series image count drifted",
        )
        manifest_sha = require_sha256(
            frozen.get("manifest_sha256"), "D1 series manifest SHA256 is invalid"
        )
        require(
            manifest_sha == runtime_series.get("manifest_sha256"),
            "D1 series manifest SHA256 drifted",
        )
        ordered_images = frozen.get("ordered_images")
        require(
            isinstance(ordered_images, list)
            and len(ordered_images) == len(runtime_images),
            "D1 ordered image snapshot is invalid",
        )
        require(
            canonical_sha256(ordered_images) == manifest_sha,
            "D1 ordered image manifest does not reproduce its SHA256",
        )
        expected_image_facts = [
            {
                "image_id": image.get("id"),
                "series_id": image.get("series_id"),
                "logical_image_key": image.get("logical_image_key"),
                "image_version_no": image.get("image_version_no"),
                "sequence_no": image.get("sequence_no"),
                "image_role": image.get("image_role"),
                "image_kind": image.get("image_kind"),
                "file_format": image.get("file_format"),
                "projection": image.get("projection"),
                "projection_provenance": image.get("projection_provenance"),
                "storage_profile": image.get("storage_profile"),
                "object_key": image.get("object_key"),
                "object_version_id": image.get("object_version_id"),
                "sha256": image.get("sha256"),
                "size_bytes": image.get("size_bytes"),
                "content_type": image.get("content_type"),
            }
            for image in runtime_images
        ]
        require(
            ordered_images == expected_image_facts,
            "D1 frozen per-image facts drifted",
        )
        series_manifest_sha256[series_id] = manifest_sha
        study_manifest_items.append(
            {
                "series_id": series_id,
                "series_key": frozen.get("series_key"),
                "series_no": frozen.get("series_no"),
                "actual_image_count": frozen.get("actual_image_count"),
                "manifest_sha256": manifest_sha,
            }
        )
    study_manifest_items.sort(
        key=lambda item: (
            item["series_no"] is None,
            item["series_no"] if item["series_no"] is not None else 0,
            item["series_key"],
            item["series_id"],
        )
    )
    require(
        canonical_sha256(study_manifest_items)
        == snapshot.get("resolved_manifest_sha256"),
        "D1 Study manifest does not reproduce its SHA256",
    )
    return {
        "context_sha256": expected_context_sha,
        "series_manifest_sha256": series_manifest_sha256,
        "config_key": snapshot.get("config_key"),
        "config_sha256": snapshot.get("config_sha256"),
        "prompt_content_sha256": snapshot.get("prompt_content_sha256"),
        "config_fingerprint": {
            key: snapshot.get(key)
            for key in (
                "ai_config_id",
                "config_key",
                "config_sha256",
                "prompt_content_sha256",
                "model_snapshot_sha256",
                "output_schema_sha256",
                "compiled_pipeline_sha256",
                "profile_key",
            )
        },
    }


def validate_reports(
    client: RuntimeClient,
    *,
    task: dict[str, Any],
    images: list[dict[str, Any]],
    series_manifest_sha256: dict[str, str],
) -> dict[str, Any]:
    task_id = task["id"]
    current = client.call("GET", "/reports/current", params={"task_id": task_id})
    history = client.call("GET", "/reports/history", params={"task_id": task_id})
    require(isinstance(current, dict), "current Report is missing")
    require(isinstance(history, list) and history, "Report history is empty")
    latest = history[0]
    require(isinstance(latest, dict), "latest Report is invalid")
    require(current.get("status") == "final", "current Report is not final")
    require(
        current.get("id") == latest.get("id") == task.get("current_report_id"),
        "Task/current/history Report IDs disagree",
    )
    content_sha = require_sha256(
        current.get("content_sha256"), "current Report content SHA256 is invalid"
    )
    require(
        latest.get("content_sha256") == content_sha,
        "current/history Report content SHA256 values disagree",
    )
    content = current.get("content_json")
    require(isinstance(content, dict), "current Report content contract is invalid")
    result = content.get("complete_medical_result")
    require(isinstance(result, dict), "CompleteMedicalResult is missing")
    require(
        result.get("result_schema_version") == COMPLETE_RESULT_VERSION,
        "CompleteMedicalResult version is not v2",
    )

    source_refs = result.get("source_refs")
    findings = result.get("findings")
    require(isinstance(source_refs, list), "CompleteMedicalResult source_refs is invalid")
    require(isinstance(findings, list), "CompleteMedicalResult findings is invalid")
    source_ref_ids: set[str] = set()
    images_by_id = {item.get("id"): item for item in images}
    require(len(images_by_id) == len(images), "Runtime Image IDs are invalid")
    for source_ref in source_refs:
        require(isinstance(source_ref, dict), "CompleteMedicalResult source ref is invalid")
        source_ref_id = source_ref.get("source_ref_id")
        require(
            isinstance(source_ref_id, str)
            and bool(source_ref_id)
            and source_ref_id not in source_ref_ids,
            "CompleteMedicalResult source ref ID is invalid",
        )
        source_ref_ids.add(source_ref_id)
        image = images_by_id.get(source_ref.get("image_id"))
        require(image is not None, "Report source image escaped the frozen input set")
        series_id = image.get("series_id")
        require(source_ref.get("series_id") == series_id, "Report source series ID drifted")
        require(
            source_ref.get("projection") == image.get("projection"),
            "Report source projection drifted",
        )
        require(
            source_ref.get("manifest_sha256")
            == series_manifest_sha256.get(series_id),
            "Report source manifest SHA256 drifted",
        )
    finding_ids: set[str] = set()
    for finding in findings:
        require(isinstance(finding, dict), "CompleteMedicalResult finding is invalid")
        finding_id = finding.get("finding_id")
        require(
            isinstance(finding_id, str)
            and bool(finding_id)
            and finding_id not in finding_ids,
            "CompleteMedicalResult finding ID is invalid",
        )
        finding_ids.add(finding_id)
        refs = finding.get("source_ref_ids")
        require(
            isinstance(refs, list)
            and refs
            and all(ref in source_ref_ids for ref in refs),
            "CompleteMedicalResult finding source refs are invalid",
        )
    return {
        "report_id": current["id"],
        "report_status": current["status"],
        "content_sha256": content_sha,
        "result_schema_version": result["result_schema_version"],
        "source_ref_count": len(source_refs),
        "finding_count": len(findings),
    }


async def _read_runtime_receipt(
    *, task_id: str, image_count: int, snapshot: dict[str, Any]
) -> dict[str, Any]:
    repository_root = str(Path(__file__).resolve().parents[2])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)

    from apps.backend.core.async_db import session_factory
    from apps.backend.crud.ai_call import AICallDal

    async with session_factory() as session:
        calls = await AICallDal(session).list_for_task(task_id)
    image_calls = [item for item in calls if item.image_count_requested > 0]
    require(len(image_calls) == 1, "global Primary Task did not have exactly one image call")
    call = image_calls[0]
    require(call.image_count_requested == image_count, "AI Call requested image count drifted")
    require(call.image_count_sent == image_count, "AI Call sent image count drifted")
    require(call.status == "succeeded", "AI Call is not succeeded")
    require(
        call.requested_image_manifest_sha256 == snapshot.get("resolved_manifest_sha256")
        and call.sent_image_manifest_sha256 == snapshot.get("resolved_manifest_sha256"),
        "AI Call Study manifest SHA256 drifted",
    )
    receipt = call.image_receipt_json
    require(isinstance(receipt, dict), "AI image receipt is missing")
    require(receipt.get("contract_version") == "ai-image-receipt.v2", "AI image receipt is not v2")
    require(receipt.get("image_count") == image_count, "AI image receipt count drifted")
    receipt_images = receipt.get("images")
    require(
        isinstance(receipt_images, list) and len(receipt_images) == image_count,
        "AI image receipt items are invalid",
    )
    frozen_series = snapshot.get("series")
    require(isinstance(frozen_series, list), "Task Snapshot Series are invalid")
    frozen_by_image_id: dict[str, tuple[str, dict[str, Any]]] = {}
    for series in frozen_series:
        require(isinstance(series, dict), "Task Snapshot Series item is invalid")
        manifest_sha256 = require_sha256(
            series.get("manifest_sha256"),
            "Task Snapshot Series manifest SHA256 is invalid",
        )
        ordered_images = series.get("ordered_images")
        require(isinstance(ordered_images, list), "Task Snapshot images are invalid")
        for image in ordered_images:
            require(isinstance(image, dict), "Task Snapshot image item is invalid")
            image_id = image.get("image_id")
            require(
                isinstance(image_id, str) and image_id not in frozen_by_image_id,
                "Task Snapshot image ID is invalid",
            )
            frozen_by_image_id[image_id] = (manifest_sha256, image)
    for receipt_image in receipt_images:
        require(isinstance(receipt_image, dict), "AI image receipt item is invalid")
        frozen = frozen_by_image_id.get(receipt_image.get("image_id"))
        require(frozen is not None, "AI image receipt escaped the frozen input set")
        series_manifest, frozen_image = frozen
        require(
            receipt_image.get("series_manifest_sha256") == series_manifest
            and receipt_image.get("sha256") == frozen_image.get("sha256")
            and receipt_image.get("projection") == frozen_image.get("projection"),
            "AI image receipt facts drifted",
        )
    receipt_image_ids = [item.get("image_id") for item in receipt_images]
    require(
        len(set(receipt_image_ids)) == image_count
        and set(receipt_image_ids) == set(frozen_by_image_id),
        "AI image receipt image identity set drifted",
    )
    return {
        "ai_call_id": call.id,
        "receipt_contract_version": receipt["contract_version"],
        "receipt_image_count": receipt["image_count"],
        "sent_image_manifest_sha256": call.sent_image_manifest_sha256,
    }


def run_once(
    client: RuntimeClient,
    *,
    args: argparse.Namespace,
    case: dict[str, Any],
    clinical_context: dict[str, Any] | None,
    run_number: int,
) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    recorded_now = utc_iso(datetime.now(timezone.utc))
    print(
        f"[{run_number}/{args.repeat}] starting case={case['case_key']} "
        f"images={case['image_count']}"
    )

    session = client.call(
        "POST",
        "/sessions",
        payload={
            "source_system": "ms-image-local-e2e",
            "source_session_id": f"session-{run_id}",
            "subject_id": "ms-image-local-e2e",
            "request_id": f"session-request-{run_id}",
            "started_at": recorded_now,
        },
    )
    require(isinstance(session, dict), "Session response is invalid")

    study_payload: dict[str, Any] = {
        "session_id": session["id"],
        "source_study_id": f"study-{run_id}",
        "modality_type": "xray",
        "metadata_schema_version": "imaging.metadata.v1",
        "expected_image_count": case["image_count"],
        "identity_status": "confirmed",
        "acquired_at": recorded_now,
    }
    if case.get("body_part") is not None:
        study_payload["body_part"] = case["body_part"]
    study = client.call("POST", "/studies", payload=study_payload)
    require(isinstance(study, dict), "Study response is invalid")

    runtime_series: list[dict[str, Any]] = []
    prepared: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for source_series in case["series"]:
        series = client.call(
            "POST",
            "/series",
            payload={
                "study_id": study["id"],
                "series_key": source_series["series_key"],
                "series_no": source_series["series_no"],
                "metadata_schema_version": "imaging.metadata.v1",
                "expected_image_count": len(source_series["images"]),
                "acquired_at": recorded_now,
            },
        )
        require(isinstance(series, dict), "Series response is invalid")
        runtime_series.append(series)
        for source_image in source_series["images"]:
            ticket = client.call(
                "POST",
                "/images/prepare-upload",
                payload={
                    "series_id": series["id"],
                    "logical_image_key": (
                        f"image-{run_id}-{source_image['sequence_no']}"
                    ),
                    "sequence_no": source_image["sequence_no"],
                    "image_role": "original",
                    "image_kind": "instance",
                    "metadata_schema_version": "imaging.metadata.v1",
                    "file_format": source_image["file_format"],
                    "expected_sha256": source_image["sha256"],
                    "expected_size_bytes": source_image["size_bytes"],
                    "declared_content_type": source_image["content_type"],
                    "projection": source_image["projection"],
                },
            )
            require(isinstance(ticket, dict), "Image upload ticket is invalid")
            ticket_image = ticket.get("image")
            require(isinstance(ticket_image, dict), "Image upload ticket omitted image")
            require(
                isinstance(ticket.get("signed_url"), str),
                "Image upload ticket omitted URL",
            )
            required_headers = ticket.get("required_headers")
            require(isinstance(required_headers, dict), "Image upload headers are invalid")
            try:
                upload = httpx.put(
                    ticket["signed_url"],
                    content=source_image["content"],
                    headers=required_headers,
                    timeout=60,
                )
            except httpx.RequestError as exc:
                raise E2EError("object upload transport failed") from exc
            require(
                upload.status_code < 400,
                f"object upload returned HTTP {upload.status_code}",
            )
            completed_image = client.call(
                "POST",
                "/images/complete-upload",
                payload={
                    "id": ticket_image["id"],
                    "expected_state_version": ticket_image["state_version"],
                    "generation": ticket["generation"],
                    "trace_id": (
                        f"image-trace-{run_id}-{source_image['sequence_no']}"
                    ),
                },
            )
            require(
                isinstance(completed_image, dict),
                "complete-upload response is invalid",
            )
            prepared.append((ticket_image, source_image, series))

    images: list[dict[str, Any]] = []
    for ticket_image, source_image, series in prepared:
        image = wait_for_image(client, ticket_image["id"])
        validate_image(
            image,
            image_id=ticket_image["id"],
            series_id=series["id"],
            projection=source_image["projection"],
            image_sha256=source_image["sha256"],
            image_size=source_image["size_bytes"],
            content_type=source_image["content_type"],
        )
        images.append(image)

    study_detail = client.call("GET", "/studies", params={"id": study["id"]})
    require(isinstance(study_detail, dict), "Study detail response is invalid")
    current_study = study_detail.get("study")
    current_series = study_detail.get("series")
    require(isinstance(current_study, dict), "Study detail omitted Study")
    require(
        isinstance(current_series, list)
        and len(current_series) == len(runtime_series),
        "Study detail series contract is invalid",
    )
    current_series_by_id = {
        item.get("id"): item for item in current_series if isinstance(item, dict)
    }
    require(
        len(current_series_by_id) == len(runtime_series),
        "Study detail Series IDs are invalid",
    )
    for source_series, created_series in zip(
        case["series"], runtime_series, strict=True
    ):
        current = current_series_by_id.get(created_series["id"])
        require(current is not None, "Study series ID drifted")
        require(current.get("status") == "ready", "Series is not ready")
        require(
            current.get("actual_image_count") == len(source_series["images"]),
            "Series image count drifted",
        )
        require_sha256(
            current.get("manifest_sha256"), "Series manifest SHA256 is invalid"
        )
    current_series = list(current_series_by_id.values())

    finalized_study = client.call(
        "POST",
        "/studies/finalize",
        payload={
            "id": study["id"],
            "expected_state_version": current_study["state_version"],
            "current_revision_id": current_study["revision_id"],
        },
    )
    require(isinstance(finalized_study, dict), "Study finalize response is invalid")
    require(finalized_study.get("status") == "ready", "Study did not finalize as ready")
    require_sha256(
        finalized_study.get("resolved_manifest_sha256"),
        "Study resolved manifest SHA256 is invalid",
    )
    revision_id = finalized_study.get("revision_id")
    require(isinstance(revision_id, str) and bool(revision_id), "Study revision ID is missing")

    task_payload: dict[str, Any] = {
        "study_id": study["id"],
        "study_revision_id": revision_id,
        "request_id": f"task-request-{run_id}",
        "task_type": "diagnose",
        "species": case["species"],
        "trace_id": f"task-trace-{run_id}",
    }
    if clinical_context is not None:
        task_payload["clinical_context"] = clinical_context
    created_task = client.call("POST", "/tasks", payload=task_payload)
    require(isinstance(created_task, dict), "Task create response is invalid")
    task = wait_for_task(client, created_task["id"])
    require(task.get("finished_at") is not None, "completed Task omitted finished_at")
    require(
        isinstance(task.get("current_report_id"), str) and bool(task["current_report_id"]),
        "completed Task omitted current_report_id",
    )
    snapshot_evidence = validate_snapshot(
        task,
        study=finalized_study,
        series=current_series,
        images=images,
        clinical_context=clinical_context,
        species=case["species"],
        expected_config_key=args.expected_config_key,
        expected_prompt_sha256=args.expected_prompt_sha256,
    )
    report_evidence = validate_reports(
        client,
        task=task,
        images=images,
        series_manifest_sha256=snapshot_evidence["series_manifest_sha256"],
    )
    receipt_evidence: dict[str, Any] = {}
    if args.verify_runtime_receipt:
        snapshot = task.get("request_snapshot_json")
        require(isinstance(snapshot, dict), "Task Snapshot is missing")
        receipt_evidence = asyncio.run(
            _read_runtime_receipt(
                task_id=task["id"],
                image_count=case["image_count"],
                snapshot=snapshot,
            )
        )

    evidence = {
        "qualification_status": "PASS",
        "run": run_number,
        "case_key": case["case_key"],
        "grouping_status": case["grouping_status"],
        "case_manifest_sha256": case["manifest_sha256"],
        "species": case["species"],
        "image_count": case["image_count"],
        "series_count": len(runtime_series),
        "session_id": session["id"],
        "study_id": study["id"],
        "revision_id": revision_id,
        "series_ids": [item["id"] for item in runtime_series],
        "image_ids": [item["id"] for item in images],
        "image_sha256": [item["sha256"] for item in images],
        "task_id": task["id"],
        "task_status": task["execution_status"],
        "medical_status": task["ai_medical_status"],
        **snapshot_evidence,
        **report_evidence,
        **receipt_evidence,
    }
    print(
        f"[{run_number}/{args.repeat}] completed task={task['id']} "
        f"report={report_evidence['report_id']}"
    )
    return evidence


def validate_batch(evidence: list[dict[str, Any]]) -> None:
    require(bool(evidence), "No E2E evidence was produced")
    require(
        len({item["context_sha256"] for item in evidence}) == 1,
        "clinical context SHA256 drifted between runs",
    )
    config_fingerprints = {
        canonical_sha256(item["config_fingerprint"]) for item in evidence
    }
    require(
        len(config_fingerprints) == 1,
        "Prompt/Config fingerprint drifted between runs",
    )
    require(
        len({item["case_manifest_sha256"] for item in evidence}) == 1,
        "case manifest SHA256 drifted between runs",
    )


def build_legacy_single_image_case(args: argparse.Namespace) -> dict[str, Any]:
    try:
        content = args.image.read_bytes()
    except OSError as exc:
        raise E2EError("image file could not be read") from exc
    require(bool(content), "image file is empty")
    file_format, content_type = image_media_type(args.image)
    sha256 = hashlib.sha256(content).hexdigest()
    raw_fingerprint = {
        "mode": "legacy_single_image",
        "species": args.species,
        "sha256": sha256,
        "projection": args.projection,
    }
    return {
        "contract_version": "legacy-single-image.v1",
        "case_key": "legacy-single-image",
        "grouping_status": "legacy_single_image",
        "species": args.species,
        "modality_type": "xray",
        "body_part": args.body_part,
        "image_count": 1,
        "manifest_sha256": canonical_sha256(raw_fingerprint),
        "series": [
            {
                "series_key": "series-1",
                "series_no": 1,
                "images": [
                    {
                        "path": args.image,
                        "content": content,
                        "sha256": sha256,
                        "size_bytes": len(content),
                        "file_format": file_format,
                        "content_type": content_type,
                        "sequence_no": 1,
                        "projection": args.projection,
                    }
                ],
            }
        ],
    }


def public_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in evidence:
        public = dict(item)
        public.pop("config_fingerprint", None)
        sanitized.append(public)
    return sanitized


def write_evidence(
    *, evidence_dir: Path, case_key: str, evidence: list[dict[str, Any]]
) -> None:
    try:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = evidence_dir / f"{case_key}-{suffix}-{uuid.uuid4().hex[:8]}.json"
        target.write_text(
            json.dumps(public_evidence(evidence), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise E2EError("sanitized evidence could not be written") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    clinical_context = build_clinical_context(args)
    case = (
        load_case_manifest(args.case_manifest)
        if args.case_manifest is not None
        else build_legacy_single_image_case(args)
    )
    token = issue_dev_token()
    client = RuntimeClient(api_base=args.api_base, token=token)
    evidence: list[dict[str, Any]] = []
    try:
        for run_number in range(1, args.repeat + 1):
            evidence.append(
                run_once(
                    client,
                    args=args,
                    case=case,
                    clinical_context=clinical_context,
                    run_number=run_number,
                )
            )
        validate_batch(evidence)
    finally:
        client.close()

    printable_evidence = public_evidence(evidence)
    if args.evidence_dir is not None:
        write_evidence(
            evidence_dir=args.evidence_dir,
            case_key=case["case_key"],
            evidence=evidence,
        )
    print("E2E_COMPLETE")
    print(json.dumps(printable_evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except E2EError as exc:
        print(f"E2E_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
