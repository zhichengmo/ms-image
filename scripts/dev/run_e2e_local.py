#!/usr/bin/env python3
"""Run repeatable local XRay engineering E2E checks via the public Runtime API.

This tool verifies public Image, Study, Task, Report or Anatomy Localization
contracts. Optional runtime-receipt verification reads the existing audit
records without mutating them. It does not infer medical facts or print
credentials, signed URLs, clinical text, Provider responses or report content.
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
ANATOMY_LOCALIZATION_RESULT_VERSION = "xray-anatomy-localization.v1"
ANATOMY_LABEL_VERSION = "xray-anatomy-labels.v1"
ANATOMY_LOCALIZATION_PROFILE = "xray_anatomy_localization_v1"
FULL_CHAIN_HARNESS_TASK_TYPE = "diagnose_full_chain"
FULL_CHAIN_RUNTIME_TASK_TYPE = "diagnose"
FULL_CHAIN_PROFILE = "xray_diagnose_full_chain_v1"
FULL_CHAIN_EXPERIMENT_SCOPE = "full-chain-local-v1"
FULL_CHAIN_ROOT_CONFIG_ID = "95914f0e47a0483692ce21377e30dba7"
FULL_CHAIN_ROOT_CONFIG_VERSION = "6.0.0"
FULL_CHAIN_MODEL_POOL_ID = "a8a4b761670745ca98e59d31073a9628"
FULL_CHAIN_REQUESTED_MODEL = "gemini-3.5-flash"
FULL_CHAIN_STAGE_CONFIG_IDS = {
    "study_screening": "0712f1535ad1436c8aca9ac5cfb460bd",
    "system_analysis": "7985cea39b0f4a959b8a4497d2f0f013",
    "joint_primary_reader": FULL_CHAIN_ROOT_CONFIG_ID,
    "targeted_review": "56e2e22c527645fba38a3a86d7d2ff7e",
    "report_generation": "f0674d515fa447579875a00e07792651",
}
FULL_CHAIN_STAGE_TOPOLOGY = (
    ("study_preparation", "study_preparation", "v1"),
    ("study_screening", "study_screening", "v2"),
    ("system_analysis", "system_analysis", "v1"),
    ("joint_primary_reader", "joint_primary_reader", "v2"),
    ("family_routing", "family_routing", "v2"),
    ("targeted_review", "targeted_review", "v2"),
    ("decision_finalization", "decision_finalization", "v2"),
    ("report_generation", "report_generation", "v1"),
)
QUALITY_STAGE_TOPOLOGY = (
    ("study_preparation", "study_preparation", "v1"),
    ("batch_image_quality_review", "batch_image_quality_review", "v1"),
)
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
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
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
        raise E2EError(
            "image extension is not supported by the upload contract"
        ) from exc


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
    require(
        isinstance(relative, str) and bool(relative.strip()), "image path is invalid"
    )
    relative_path = Path(relative)
    require(
        not relative_path.is_absolute() and ".." not in relative_path.parts,
        "image path must be relative to the configured data root",
    )
    path = (data_root / relative_path).resolve()
    require(
        path.is_relative_to(data_root), "image path escaped the configured data root"
    )
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
    require(
        raw.get("contract_version") == CASE_MANIFEST_VERSION,
        "case manifest version is invalid",
    )
    require(
        raw.get("grouping_status") == "engineering_candidate",
        "case grouping status is invalid",
    )
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
    require(
        isinstance(raw_series, list) and raw_series, "case manifest series are invalid"
    )
    series_rows: list[dict[str, Any]] = []
    sequence_numbers: list[int] = []
    series_keys: set[str] = set()
    for index, item in enumerate(raw_series, 1):
        require(isinstance(item, dict), "case manifest series item is invalid")
        require(
            set(item) == {"series_key", "images"},
            "case manifest series fields are invalid",
        )
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
    parser.add_argument(
        "--task-type",
        choices=("diagnose", FULL_CHAIN_HARNESS_TASK_TYPE, "anatomy_localization"),
        default="diagnose",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--case-manifest", type=Path)
    parser.add_argument("--species", choices=("cat", "dog"))
    parser.add_argument("--projection", type=non_empty_projection)
    parser.add_argument("--body-part", type=optional_non_empty)
    parser.add_argument(
        "--clinical-context-mode",
        choices=("synthetic", "none"),
        default=None,
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
    if args.task_type in {"diagnose", FULL_CHAIN_HARNESS_TASK_TYPE}:
        args.clinical_context_mode = args.clinical_context_mode or "synthetic"
        if args.task_type == FULL_CHAIN_HARNESS_TASK_TYPE:
            if args.case_manifest is None:
                parser.error(
                    "diagnose_full_chain requires a 2-to-5-image --case-manifest"
                )
            if args.repeat != 1:
                parser.error("diagnose_full_chain requires --repeat=1")
            if not args.verify_runtime_receipt:
                parser.error(
                    "diagnose_full_chain requires --verify-runtime-receipt"
                )
            if (
                os.environ.get("XRAY_TARGETED_EXPERIMENT_SCOPE_KEY", "").strip()
                != FULL_CHAIN_EXPERIMENT_SCOPE
            ):
                parser.error(
                    "diagnose_full_chain requires "
                    "XRAY_TARGETED_EXPERIMENT_SCOPE_KEY=full-chain-local-v1"
                )
            if args.expected_prompt_sha256 is not None:
                parser.error(
                    "diagnose_full_chain audits each Stage Prompt and does not "
                    "accept one global --expected-prompt-sha256"
                )
    else:
        if args.case_manifest is None:
            parser.error("anatomy_localization requires --case-manifest")
        if args.repeat != 1:
            parser.error("anatomy_localization requires --repeat=1")
        if args.clinical_context_mode == "synthetic":
            parser.error("anatomy_localization does not accept clinical context")
        if args.context_recorded_at is not None:
            parser.error("anatomy_localization does not accept --context-recorded-at")
        if not args.verify_runtime_receipt:
            parser.error("anatomy_localization requires --verify-runtime-receipt")
        args.clinical_context_mode = "none"
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
    if (
        args.verify_runtime_receipt
        and args.case_manifest is None
        and args.task_type != FULL_CHAIN_HARNESS_TASK_TYPE
    ):
        parser.error("--verify-runtime-receipt requires --case-manifest")
    if (
        args.verify_runtime_receipt
        and args.task_type != FULL_CHAIN_HARNESS_TASK_TYPE
        and args.expected_config_key is None
    ):
        parser.error("--verify-runtime-receipt requires --expected-config-key")
    if (
        args.verify_runtime_receipt
        and args.task_type != FULL_CHAIN_HARNESS_TASK_TYPE
        and args.expected_prompt_sha256 is None
    ):
        parser.error("--verify-runtime-receipt requires --expected-prompt-sha256")
    if args.verify_runtime_receipt and args.evidence_dir is None:
        parser.error("--verify-runtime-receipt requires --evidence-dir")
    if args.evidence_dir is not None:
        args.evidence_dir = args.evidence_dir.expanduser().resolve()
    if args.clinical_context_mode == "none" and args.context_recorded_at is not None:
        parser.error("--context-recorded-at requires synthetic context mode")
    if (
        args.task_type != FULL_CHAIN_HARNESS_TASK_TYPE
        and (args.expected_config_key is None)
        != (args.expected_prompt_sha256 is None)
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
            raise E2EError(f"{method} {endpoint} returned HTTP {response.status_code}")
        try:
            envelope = response.json()
        except ValueError as exc:
            raise E2EError(f"{method} {endpoint} returned invalid JSON") from exc
        require(isinstance(envelope, dict), f"{method} {endpoint} envelope is invalid")
        require(
            envelope.get("success") is True, f"{method} {endpoint} was unsuccessful"
        )
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
        snapshot.get("resolved_manifest_sha256")
        == study.get("resolved_manifest_sha256"),
        "Study manifest SHA drifted in Task Snapshot",
    )
    require(snapshot.get("species") == species, "Task Snapshot species drifted")
    if expected_config_key is not None:
        require(
            snapshot.get("config_key") == expected_config_key,
            "Task Snapshot Config key did not match the qualified species route",
        )
    if expected_prompt_sha256 is not None:
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
    require(
        isinstance(source_refs, list), "CompleteMedicalResult source_refs is invalid"
    )
    require(isinstance(findings, list), "CompleteMedicalResult findings is invalid")
    source_ref_ids: set[str] = set()
    images_by_id = {item.get("id"): item for item in images}
    require(len(images_by_id) == len(images), "Runtime Image IDs are invalid")
    for source_ref in source_refs:
        require(
            isinstance(source_ref, dict), "CompleteMedicalResult source ref is invalid"
        )
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
        require(
            source_ref.get("series_id") == series_id, "Report source series ID drifted"
        )
        require(
            source_ref.get("projection") == image.get("projection"),
            "Report source projection drifted",
        )
        require(
            source_ref.get("manifest_sha256") == series_manifest_sha256.get(series_id),
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


def validate_no_reports(
    client: RuntimeClient,
    *,
    task: dict[str, Any],
) -> dict[str, Any]:
    task_id = task["id"]
    current = client.call("GET", "/reports/current", params={"task_id": task_id})
    history = client.call("GET", "/reports/history", params={"task_id": task_id})
    require(task.get("current_report_id") is None, "Localization Task created a Report")
    require(current is None, "Localization Task has a current Report")
    require(history == [], "Localization Task has Report history")
    return {
        "report_required": False,
        "current_report_id": None,
        "report_history_count": 0,
    }


def _snapshot_localization_lineage(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    frozen_series = snapshot.get("series")
    require(isinstance(frozen_series, list), "Task Snapshot Series are invalid")
    lineage: list[dict[str, Any]] = []
    for series in frozen_series:
        require(isinstance(series, dict), "Task Snapshot Series item is invalid")
        series_id = series.get("series_id")
        manifest_sha256 = require_sha256(
            series.get("manifest_sha256"),
            "Task Snapshot Series manifest SHA256 is invalid",
        )
        ordered_images = series.get("ordered_images")
        require(isinstance(ordered_images, list), "Task Snapshot images are invalid")
        for image in ordered_images:
            require(isinstance(image, dict), "Task Snapshot image item is invalid")
            lineage.append(
                {
                    "image_id": image.get("image_id"),
                    "series_id": series_id,
                    "sequence_no": image.get("sequence_no"),
                    "projection": image.get("projection"),
                    "series_manifest_sha256": manifest_sha256,
                }
            )
    require(
        len({item["image_id"] for item in lineage}) == len(lineage),
        "Task Snapshot image ID is duplicated",
    )
    return lineage


def validate_anatomy_localization(
    client: RuntimeClient,
    *,
    task: dict[str, Any],
    study: dict[str, Any],
    image_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    response = client.call(
        "GET",
        "/anatomy-localizations",
        params={"task_id": task["id"]},
    )
    require(isinstance(response, dict), "Anatomy Localization response is invalid")
    require(response.get("task_id") == task["id"], "Localization Task ID drifted")
    require(
        response.get("study_id") == task.get("study_id"),
        "Localization Study ID drifted",
    )
    require(
        response.get("study_revision_id") == task.get("study_revision_id"),
        "Localization Study revision ID drifted",
    )
    require(
        response.get("study_id") == study.get("id"),
        "Localization result escaped its Study",
    )
    require(
        isinstance(response.get("stage_checkpoint_id"), str)
        and bool(response["stage_checkpoint_id"]),
        "Localization Stage checkpoint ID is missing",
    )
    require(
        isinstance(response.get("source_call_id"), str)
        and bool(response["source_call_id"]),
        "Localization source Call ID is missing",
    )
    output_sha256 = require_sha256(
        response.get("output_sha256"),
        "Localization Stage output SHA256 is invalid",
    )
    result = response.get("result")
    require(isinstance(result, dict), "Anatomy Localization result is invalid")
    require(
        result.get("contract_version") == ANATOMY_LOCALIZATION_RESULT_VERSION,
        "Anatomy Localization result contract drifted",
    )
    require(
        result.get("label_contract_version") == ANATOMY_LABEL_VERSION,
        "Anatomy Localization label contract drifted",
    )
    snapshot = task.get("request_snapshot_json")
    require(isinstance(snapshot, dict), "Task Snapshot is missing")
    require(
        result.get("species") == snapshot.get("species"),
        "Anatomy Localization species drifted",
    )
    result_images = result.get("images")
    require(
        isinstance(result_images, list) and len(result_images) == image_count,
        "Anatomy Localization result image count drifted",
    )
    expected_lineage = _snapshot_localization_lineage(snapshot)
    require(
        len(expected_lineage) == image_count,
        "Task Snapshot image count drifted",
    )
    for expected, actual in zip(expected_lineage, result_images, strict=True):
        require(isinstance(actual, dict), "Localization result image is invalid")
        for field in (
            "image_id",
            "series_id",
            "sequence_no",
            "projection",
            "series_manifest_sha256",
        ):
            require(
                actual.get(field) == expected[field],
                f"Localization result {field} drifted",
            )
    return response, {
        "stage_checkpoint_id": response["stage_checkpoint_id"],
        "ai_call_id": response["source_call_id"],
        "stage_output_sha256": output_sha256,
        "localization_contract_version": result["contract_version"],
        "label_contract_version": result["label_contract_version"],
        "localization_result_status": result.get("result_status"),
        "result_image_count": len(result_images),
    }


async def _read_runtime_receipt(
    *,
    task_id: str,
    task_type: str,
    image_count: int,
    snapshot: dict[str, Any],
    localization_response: dict[str, Any] | None,
) -> dict[str, Any]:
    repository_root = str(Path(__file__).resolve().parents[2])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)

    from apps.backend.core.async_db import session_factory
    from apps.backend.crud.ai_call import AICallDal
    from apps.backend.crud.ai_call_attempt import AICallAttemptDal
    from apps.backend.crud.ai_config_record import AIConfigRecordDal
    from apps.backend.crud.stage_checkpoint import StageCheckpointDal
    from apps.backend.crud.task import TaskDal

    async with session_factory() as session:
        call_dal = AICallDal(session)
        calls = await call_dal.list_for_task(task_id)
        image_calls = [item for item in calls if item.image_count_requested > 0]
        require(
            len(image_calls) == 1,
            "global Primary Task did not have exactly one image call",
        )
        call = image_calls[0]
        stages = []
        attempt_count = 0
        attempt = None
        config = None
        runtime_task = None
        if task_type == "anatomy_localization":
            stages = await StageCheckpointDal(session).list_for_task(task_id)
            runtime_task = await TaskDal(session).get_by_id(task_id)
            attempt_dal = AICallAttemptDal(session)
            attempt_count = await attempt_dal.get_count(ai_call_id=call.id)
            attempt = await attempt_dal.get_by_call_attempt_no(
                ai_call_id=call.id,
                attempt_no=1,
            )
            config_id = snapshot.get("ai_config_id")
            require(isinstance(config_id, str), "Task Snapshot Config ID is missing")
            config = await AIConfigRecordDal(session).get_by_id(config_id)

    require(
        call.image_count_requested == image_count,
        "AI Call requested image count drifted",
    )
    require(call.image_count_sent == image_count, "AI Call sent image count drifted")
    require(call.status == "succeeded", "AI Call is not succeeded")
    require(
        call.requested_image_manifest_sha256 == snapshot.get("resolved_manifest_sha256")
        and call.sent_image_manifest_sha256 == snapshot.get("resolved_manifest_sha256"),
        "AI Call Study manifest SHA256 drifted",
    )
    receipt = call.image_receipt_json
    require(isinstance(receipt, dict), "AI image receipt is missing")
    require(
        receipt.get("contract_version") == "ai-image-receipt.v2",
        "AI image receipt is not v2",
    )
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

    evidence = {
        "ai_call_id": call.id,
        "receipt_contract_version": receipt["contract_version"],
        "requested_image_count": call.image_count_requested,
        "sent_image_count": call.image_count_sent,
        "receipt_image_count": receipt["image_count"],
        "sent_image_manifest_sha256": call.sent_image_manifest_sha256,
    }
    if task_type != "anatomy_localization":
        return evidence

    require(len(calls) == 1, "Localization Task did not have exactly one Logical Call")
    require(
        call.result_disposition == "accepted", "Localization AI Call was not accepted"
    )
    require(call.attempt_count == 1, "Localization AI Call attempt count drifted")
    require(
        attempt_count == 1 and attempt is not None,
        "Localization did not have exactly one Physical Attempt",
    )
    require(attempt.ai_call_id == call.id, "Localization Attempt Call ID drifted")
    require(attempt.attempt_no == 1, "Localization Attempt number drifted")
    require(attempt.status == "succeeded", "Localization Attempt is not succeeded")
    require(
        attempt.id == call.winner_attempt_id,
        "Localization winner is not Physical Attempt #1",
    )
    require(config is not None, "Localization frozen Config is missing")
    require(runtime_task is not None, "Localization Task is missing")
    require(
        runtime_task.report_required is False
        and runtime_task.current_report_id is None
        and runtime_task.ai_medical_status == "not_produced",
        "Localization Task Report boundary drifted",
    )
    require(
        config.id == snapshot.get("ai_config_id") == call.ai_config_id,
        "Localization Config identity drifted",
    )
    require(
        config.task_type == "anatomy_localization"
        and config.profile_key == ANATOMY_LOCALIZATION_PROFILE,
        "Localization Config task/profile binding drifted",
    )
    require(
        config.config_sha256 == snapshot.get("config_sha256") == call.config_sha256,
        "Localization Config SHA256 drifted",
    )
    require(
        config.output_schema_sha256 == snapshot.get("output_schema_sha256")
        and call.schema_sha256 == config.output_schema_sha256,
        "Localization Schema SHA256 drifted",
    )
    require(
        config.compiled_pipeline_sha256 == snapshot.get("compiled_pipeline_sha256"),
        "Localization Pipeline SHA256 drifted",
    )
    output_schema = config.output_schema_json
    require(isinstance(output_schema, dict), "Localization output Schema is missing")
    require(
        output_schema.get("x-ms-image-contract-version")
        == ANATOMY_LOCALIZATION_RESULT_VERSION,
        "Localization output Schema contract drifted",
    )
    budget = config.budget_policy_json
    require(isinstance(budget, dict), "Localization budget policy is missing")
    require(budget.get("max_input_images") == 5, "Localization image budget drifted")
    require(budget.get("max_total_calls") == 1, "Localization Call budget drifted")
    require(
        budget.get("max_total_attempts") == 1, "Localization Attempt budget drifted"
    )
    model_snapshot = config.model_snapshot_json
    require(isinstance(model_snapshot, dict), "Localization model snapshot is missing")
    lanes = model_snapshot.get("lanes")
    require(
        isinstance(lanes, list) and len(lanes) == 1, "Localization lane count drifted"
    )
    lane = lanes[0]
    require(
        isinstance(lane, dict)
        and lane.get("lane_key") == "primary"
        and lane.get("max_attempts") == 1,
        "Localization primary lane contract drifted",
    )
    require(
        len(stages) == 2
        and stages[0].stage_no == 1
        and stages[0].stage_key == "study_preparation"
        and stages[0].handler_key == "study_preparation"
        and stages[0].handler_version == "v1"
        and stages[0].status == "completed"
        and stages[1].stage_no == 2
        and stages[1].stage_key == "anatomy_localization"
        and stages[1].handler_key == "anatomy_localization"
        and stages[1].handler_version == "v1"
        and stages[1].status == "completed",
        "Localization Stage topology drifted",
    )
    localization_stage = stages[1]
    require(
        call.stage_checkpoint_id == localization_stage.id,
        "Localization Call Stage ID drifted",
    )
    stage_output = localization_stage.output_json
    require(isinstance(stage_output, dict), "Localization Stage output is missing")
    require(
        stage_output.get("source_call_id") == call.id,
        "Localization Stage source Call ID drifted",
    )
    require(
        isinstance(localization_response, dict),
        "Localization public response was not supplied for audit verification",
    )
    result = localization_response.get("result")
    require(isinstance(result, dict), "Localization public result is invalid")
    require(
        call.parsed_result_json
        == stage_output.get("anatomy_localization_result")
        == result,
        "Localization Call, Stage and query results disagree",
    )
    require(
        localization_response.get("stage_checkpoint_id") == localization_stage.id
        and localization_response.get("source_call_id") == call.id
        and localization_response.get("output_sha256")
        == localization_stage.output_sha256,
        "Localization public response lineage drifted",
    )
    expected_lineage = _snapshot_localization_lineage(snapshot)
    for expected, receipt_image, result_image in zip(
        expected_lineage,
        receipt_images,
        result["images"],
        strict=True,
    ):
        for field in (
            "image_id",
            "series_id",
            "sequence_no",
            "projection",
            "series_manifest_sha256",
        ):
            require(
                receipt_image.get(field) == expected[field]
                and result_image.get(field) == expected[field],
                f"Localization Snapshot/receipt/result {field} drifted",
            )

    evidence.update(
        {
            "attempt_id": attempt.id,
            "attempt_no": attempt.attempt_no,
            "attempt_count": attempt_count,
            "lane_key": lane["lane_key"],
            "lane_max_attempts": lane["max_attempts"],
            "ai_config_id": config.id,
            "config_sha256": config.config_sha256,
            "prompt_content_sha256": config.prompt_content_sha256,
            "output_schema_sha256": config.output_schema_sha256,
            "model_snapshot_sha256": config.model_snapshot_sha256,
            "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
            "result_image_count": len(result["images"]),
        }
    )
    return evidence


def _require_stage_topology(
    stages: list[Any],
    expected: tuple[tuple[str, str, str], ...],
    *,
    label: str,
) -> None:
    actual = [
        (stage.stage_key, stage.handler_key, stage.handler_version)
        for stage in stages
    ]
    require(actual == list(expected), f"{label} Stage topology drifted")
    for stage_no, stage in enumerate(stages, start=1):
        require(stage.stage_no == stage_no, f"{label} Stage number drifted")
        require(stage.status == "completed", f"{label} Stage is not completed")
        require(stage.retry_count == 0, f"{label} Stage retried")
        require(stage.error_code is None, f"{label} Stage retained an error")
        require(stage.finished_at is not None, f"{label} Stage omitted finished_at")


def _require_binding_matches_config(
    *, binding: dict[str, Any], config: Any, stage_key: str
) -> None:
    expected = {
        "ai_config_id": config.id,
        "config_key": config.config_key,
        "config_version": config.version,
        "profile_key": config.profile_key,
        "prompt_key": config.prompt_key,
        "activation_scope": config.activation_scope,
        "scope_key": config.scope_key,
        "config_sha256": config.config_sha256,
        "release_fingerprint": config.release_fingerprint,
        "prompt_content_sha256": config.prompt_content_sha256,
        "model_snapshot_sha256": config.model_snapshot_sha256,
        "output_schema_sha256": config.output_schema_sha256,
        "compiled_pipeline_sha256": config.compiled_pipeline_sha256,
        "stage_registry_contract_version": config.stage_registry_contract_version,
        "budget_policy_sha256": canonical_sha256(config.budget_policy_json),
    }
    require(binding == expected, f"{stage_key} frozen Config binding drifted")


async def _audit_accepted_ai_call(
    *,
    attempt_dal: Any,
    call: Any,
    stage: Any,
    config: Any,
    expected_image_count: int,
    expected_manifest_sha256: str | None,
    label: str,
) -> dict[str, Any]:
    attempt_count = await attempt_dal.get_count(ai_call_id=call.id)
    attempt = await attempt_dal.get_by_call_attempt_no(
        ai_call_id=call.id,
        attempt_no=1,
    )
    require(attempt_count == 1 and attempt is not None, f"{label} Attempt count drifted")
    require(call.stage_checkpoint_id == stage.id, f"{label} Call Stage drifted")
    require(call.status == "succeeded", f"{label} Call is not succeeded")
    require(
        call.result_disposition == "accepted",
        f"{label} Call result was not accepted",
    )
    require(call.attempt_count == 1, f"{label} Call attempt_count drifted")
    require(
        call.winner_attempt_id == attempt.id,
        f"{label} winner Attempt drifted",
    )
    require(call.error_code is None, f"{label} Call retained an error")
    require(call.finished_at is not None, f"{label} Call omitted finished_at")
    require(attempt.attempt_no == 1, f"{label} Attempt number drifted")
    require(attempt.status == "succeeded", f"{label} Attempt is not succeeded")
    require(attempt.reconcile_count == 0, f"{label} Attempt was reconciled")
    require(attempt.error_code is None, f"{label} Attempt retained an error")
    require(attempt.finished_at is not None, f"{label} Attempt omitted finished_at")

    require(
        isinstance(call.provider_request_id, str) and bool(call.provider_request_id),
        f"{label} Provider request ID is missing",
    )
    require(
        call.provider_request_id == attempt.provider_request_id,
        f"{label} Provider request ID drifted",
    )
    require(
        isinstance(call.actual_model, str) and bool(call.actual_model),
        f"{label} actual model is missing",
    )
    require(call.actual_model == attempt.actual_model, f"{label} actual model drifted")
    response_sha256 = require_sha256(
        call.response_sha256, f"{label} response SHA256 is invalid"
    )
    require(
        response_sha256 == attempt.response_sha256,
        f"{label} response SHA256 drifted",
    )
    require(
        isinstance(call.parsed_result_json, dict)
        and call.parsed_result_json == attempt.parsed_result_json,
        f"{label} parsed result is missing or drifted",
    )
    require_sha256(call.request_sha256, f"{label} request SHA256 is invalid")
    require(
        call.request_sha256 == attempt.request_sha256,
        f"{label} request SHA256 drifted",
    )
    rendered_prompt_sha256 = require_sha256(
        call.rendered_prompt_sha256,
        f"{label} rendered Prompt SHA256 is invalid",
    )
    require(
        isinstance(call.rendered_messages_json, list)
        and bool(call.rendered_messages_json)
        and all(isinstance(message, dict) for message in call.rendered_messages_json),
        f"{label} rendered Prompt messages are missing",
    )

    require(config is not None and config.id == call.ai_config_id, f"{label} Config drifted")
    require(config.config_sha256 == call.config_sha256, f"{label} Config SHA drifted")
    require(config.output_schema_sha256 == call.schema_sha256, f"{label} Schema drifted")
    require(config.status == "active", f"{label} Config is not active")
    require(
        isinstance(config.prompt_content, str) and bool(config.prompt_content.strip()),
        f"{label} Config Prompt body is missing",
    )
    prompt_content_sha256 = require_sha256(
        config.prompt_content_sha256,
        f"{label} Config Prompt SHA256 is invalid",
    )
    require(
        hashlib.sha256(config.prompt_content.encode("utf-8")).hexdigest()
        == prompt_content_sha256,
        f"{label} Config Prompt body SHA256 drifted",
    )

    require(
        call.image_count_requested == expected_image_count,
        f"{label} requested image count drifted",
    )
    require(
        call.image_count_sent == expected_image_count
        and attempt.image_count_sent == expected_image_count,
        f"{label} sent image count drifted",
    )
    receipt = call.image_receipt_json
    require(
        isinstance(receipt, dict) and receipt == attempt.image_receipt_json,
        f"{label} image receipt is missing or drifted",
    )
    require(
        receipt.get("contract_version") == "ai-image-receipt.v2",
        f"{label} image receipt is not v2",
    )
    receipt_images = receipt.get("images")
    require(
        receipt.get("image_count") == expected_image_count
        and isinstance(receipt_images, list)
        and len(receipt_images) == expected_image_count,
        f"{label} receipt image count drifted",
    )
    if expected_manifest_sha256 is not None:
        require(
            call.requested_image_manifest_sha256 == expected_manifest_sha256
            and call.sent_image_manifest_sha256 == expected_manifest_sha256
            and attempt.sent_image_manifest_sha256 == expected_manifest_sha256,
            f"{label} image manifest SHA256 drifted",
        )
    else:
        require(
            call.sent_image_manifest_sha256 == attempt.sent_image_manifest_sha256,
            f"{label} zero-image manifest SHA256 drifted",
        )

    return {
        "stage_key": stage.stage_key,
        "stage_checkpoint_id": stage.id,
        "ai_call_id": call.id,
        "attempt_id": attempt.id,
        "ai_config_id": config.id,
        "prompt_content_sha256": prompt_content_sha256,
        "rendered_prompt_sha256": rendered_prompt_sha256,
        "response_sha256": response_sha256,
        "requested_model": call.requested_model,
        "actual_model": call.actual_model,
        "image_count_requested": call.image_count_requested,
        "image_count_sent": call.image_count_sent,
        "receipt_image_count": receipt["image_count"],
        "attempt_count": attempt_count,
        "reconcile_count": attempt.reconcile_count,
    }


async def _read_full_chain_runtime_receipt(
    *,
    quality_task_id: str,
    diagnose_task_id: str,
    image_count: int,
    quality_snapshot: dict[str, Any],
    diagnose_snapshot: dict[str, Any],
) -> dict[str, Any]:
    repository_root = str(Path(__file__).resolve().parents[2])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)

    from apps.backend.core.ai.study_screening_contract import (
        XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
        canonicalize_xray_study_screening_result,
    )
    from apps.backend.core.async_db import session_factory
    from apps.backend.crud.ai_call import AICallDal
    from apps.backend.crud.ai_call_attempt import AICallAttemptDal
    from apps.backend.crud.ai_config_record import AIConfigRecordDal
    from apps.backend.crud.report import ReportDal
    from apps.backend.crud.stage_checkpoint import StageCheckpointDal
    from apps.backend.crud.task import TaskDal

    async with session_factory() as session:
        task_dal = TaskDal(session)
        stage_dal = StageCheckpointDal(session)
        call_dal = AICallDal(session)
        attempt_dal = AICallAttemptDal(session)
        config_dal = AIConfigRecordDal(session)
        report_dal = ReportDal(session)

        quality_task = await task_dal.get_by_id(quality_task_id)
        quality_stages = await stage_dal.list_for_task(quality_task_id)
        quality_calls = await call_dal.list_for_task(quality_task_id)
        quality_reports = await report_dal.list_for_task(quality_task_id)
        require(quality_task is not None, "Quality Task DB record is missing")
        require(
            quality_task.task_type == "xray_quality_control"
            and quality_task.execution_status == "completed"
            and quality_task.report_required is False
            and quality_task.current_report_id is None
            and quality_task.ai_medical_status == "not_produced",
            "Quality Task completion boundary drifted",
        )
        require(quality_reports == [], "Quality Task unexpectedly produced a Report")
        _require_stage_topology(
            quality_stages,
            QUALITY_STAGE_TOPOLOGY,
            label="Quality Task",
        )
        require(len(quality_calls) == 1, "Quality Task Call count drifted")
        quality_stage = quality_stages[1]
        quality_call = quality_calls[0]
        quality_config = await config_dal.get_by_id(quality_call.ai_config_id)
        quality_call_evidence = await _audit_accepted_ai_call(
            attempt_dal=attempt_dal,
            call=quality_call,
            stage=quality_stage,
            config=quality_config,
            expected_image_count=image_count,
            expected_manifest_sha256=quality_snapshot.get(
                "resolved_manifest_sha256"
            ),
            label="Quality Review",
        )
        require(
            quality_config.task_type == "xray_quality_control"
            and quality_config.profile_key == "xray_image_quality_v1",
            "Quality Review Config task/profile drifted",
        )
        quality_output = quality_stage.output_json
        require(
            isinstance(quality_output, dict)
            and quality_output.get("source_call_id") == quality_call.id
            and quality_output.get("xray_image_quality_result")
            == quality_call.parsed_result_json,
            "Quality Review Call/Stage result drifted",
        )

        diagnose_task = await task_dal.get_by_id(diagnose_task_id)
        diagnose_stages = await stage_dal.list_for_task(diagnose_task_id)
        diagnose_calls = await call_dal.list_for_task(diagnose_task_id)
        reports = await report_dal.list_for_task(diagnose_task_id)
        require(diagnose_task is not None, "Diagnose Task DB record is missing")
        require(
            diagnose_task.task_type == FULL_CHAIN_RUNTIME_TASK_TYPE
            and diagnose_task.execution_status == "completed"
            and diagnose_task.report_required is True
            and isinstance(diagnose_task.current_report_id, str)
            and bool(diagnose_task.current_report_id),
            "Diagnose Task completion boundary drifted",
        )
        require(
            diagnose_snapshot.get("profile_key") == FULL_CHAIN_PROFILE
            and diagnose_snapshot.get("ai_config_id") == FULL_CHAIN_ROOT_CONFIG_ID,
            "Diagnose full-chain Root Config drifted",
        )
        _require_stage_topology(
            diagnose_stages,
            FULL_CHAIN_STAGE_TOPOLOGY,
            label="Diagnose full-chain",
        )
        require(len(diagnose_calls) == 5, "Diagnose full-chain Call count drifted")
        stages_by_key = {stage.stage_key: stage for stage in diagnose_stages}
        calls_by_stage_id = {call.stage_checkpoint_id: call for call in diagnose_calls}
        require(
            len(calls_by_stage_id) == len(diagnose_calls),
            "Diagnose full-chain created duplicate Calls for one Stage",
        )

        bindings = diagnose_snapshot.get("stage_ai_config_bindings")
        expected_binding_keys = {
            "study_screening",
            "system_analysis",
            "targeted_review",
            "report_generation",
        }
        require(
            isinstance(bindings, dict) and set(bindings) == expected_binding_keys,
            "Diagnose full-chain Stage Config bindings drifted",
        )

        root_config = await config_dal.get_by_id(FULL_CHAIN_ROOT_CONFIG_ID)
        require(root_config is not None, "Diagnose Root Config is missing")
        root_budget = root_config.budget_policy_json
        require(
            root_config.config_key == "xray_diagnose_cat"
            and root_config.version == FULL_CHAIN_ROOT_CONFIG_VERSION
            and root_config.profile_key == FULL_CHAIN_PROFILE
            and root_config.task_type == FULL_CHAIN_RUNTIME_TASK_TYPE
            and root_config.model_pool_id == FULL_CHAIN_MODEL_POOL_ID
            and isinstance(root_budget, dict)
            and root_budget.get("max_total_calls") == 5
            and root_budget.get("max_total_attempts") == 5,
            "Diagnose Root Config contract drifted",
        )

        stage_call_evidence: list[dict[str, Any]] = []
        audited_calls: dict[str, Any] = {}
        for stage_key, expected_config_id in FULL_CHAIN_STAGE_CONFIG_IDS.items():
            stage = stages_by_key[stage_key]
            call = calls_by_stage_id.get(stage.id)
            require(call is not None, f"{stage_key} did not create exactly one Call")
            require(
                call.ai_config_id == expected_config_id,
                f"{stage_key} Config ID drifted",
            )
            config = await config_dal.get_by_id(expected_config_id)
            require(config is not None, f"{stage_key} Config is missing")
            require(
                config.task_type == FULL_CHAIN_RUNTIME_TASK_TYPE
                and config.model_pool_id == FULL_CHAIN_MODEL_POOL_ID,
                f"{stage_key} Config task/model pool drifted",
            )
            model_snapshot = config.model_snapshot_json
            lanes = model_snapshot.get("lanes") if isinstance(model_snapshot, dict) else None
            require(
                isinstance(lanes, list)
                and len(lanes) == 1
                and isinstance(lanes[0], dict)
                and lanes[0].get("lane_key") == "primary"
                and lanes[0].get("max_attempts") == 1
                and lanes[0].get("requested_model") == FULL_CHAIN_REQUESTED_MODEL
                and call.execution_mode == "single"
                and call.requested_model == FULL_CHAIN_REQUESTED_MODEL,
                f"{stage_key} single-lane model contract drifted",
            )
            if stage_key != "joint_primary_reader":
                binding = bindings.get(stage_key)
                require(isinstance(binding, dict), f"{stage_key} Config binding is missing")
                _require_binding_matches_config(
                    binding=binding,
                    config=config,
                    stage_key=stage_key,
                )
            expected_images = 0 if stage_key == "report_generation" else image_count
            call_evidence = await _audit_accepted_ai_call(
                attempt_dal=attempt_dal,
                call=call,
                stage=stage,
                config=config,
                expected_image_count=expected_images,
                expected_manifest_sha256=(
                    None
                    if stage_key == "report_generation"
                    else diagnose_snapshot.get("resolved_manifest_sha256")
                ),
                label=stage_key,
            )
            output = stage.output_json
            require(
                isinstance(output, dict) and output.get("source_call_id") == call.id,
                f"{stage_key} Stage source Call drifted",
            )
            if stage_key == "study_screening":
                expected_stage_result = canonicalize_xray_study_screening_result(
                    provider_result=call.parsed_result_json,
                    schema_contract_version=(
                        XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2
                    ),
                    image_receipt=call.image_receipt_json,
                    expected_species=diagnose_snapshot.get("species"),
                )
                require(
                    output.get("study_screening_result") == expected_stage_result,
                    "study_screening Provider/canonical Stage result drifted",
                )
            else:
                result_key = {
                    "system_analysis": "system_analysis_result",
                    "joint_primary_reader": "complete_medical_result",
                    "targeted_review": "complete_medical_result",
                    "report_generation": "report_generation_result",
                }[stage_key]
                require(
                    output.get(result_key) == call.parsed_result_json,
                    f"{stage_key} Call/Stage parsed result drifted",
                )
            audited_calls[stage_key] = call
            stage_call_evidence.append(call_evidence)

        route_output = stages_by_key["family_routing"].output_json
        require(
            isinstance(route_output, dict)
            and route_output.get("route_signal") == "targeted_review"
            and isinstance(route_output.get("selected_family_key"), str)
            and bool(route_output["selected_family_key"])
            and isinstance(route_output.get("selected_focus_key"), str)
            and bool(route_output["selected_focus_key"]),
            "FamilyRouting did not produce a legal TargetedReview candidate",
        )

        decision_output = stages_by_key["decision_finalization"].output_json
        report_stage = stages_by_key["report_generation"]
        report_output = report_stage.output_json
        report_call = audited_calls["report_generation"]
        frozen_medical_result = report_call.parsed_result_json.get(
            "final_medical_result"
        )
        require(
            isinstance(decision_output, dict)
            and isinstance(report_output, dict)
            and isinstance(frozen_medical_result, dict)
            and frozen_medical_result
            == decision_output.get("complete_medical_result")
            == report_output.get("complete_medical_result"),
            "ReportGeneration rewrote the frozen medical result",
        )
        require(len(reports) == 1, "Diagnose full-chain Report count drifted")
        report = reports[0]
        report_content = report.content_json
        require(
            report.id == diagnose_task.current_report_id
            and report.status == "final"
            and report.source_stage_checkpoint_id == report_stage.id
            and report.source_call_id == report_call.id
            and isinstance(report_content, dict)
            and report_content.get("complete_medical_result") == frozen_medical_result
            and report_content.get("report_generation_result")
            == report_call.parsed_result_json,
            "Diagnose full-chain final Report lineage/content drifted",
        )

    return {
        "quality_task_id": quality_task_id,
        "quality_stage_count": len(quality_stages),
        "quality_call_count": len(quality_calls),
        "quality_report_count": len(quality_reports),
        "quality_call": quality_call_evidence,
        "full_chain_profile": FULL_CHAIN_PROFILE,
        "full_chain_stage_count": len(diagnose_stages),
        "full_chain_call_count": len(diagnose_calls),
        "full_chain_attempt_count": sum(
            item["attempt_count"] for item in stage_call_evidence
        ),
        "targeted_family_key": route_output["selected_family_key"],
        "targeted_focus_key": route_output["selected_focus_key"],
        "report_generation_image_counts": {
            "requested": stage_call_evidence[-1]["image_count_requested"],
            "sent": stage_call_evidence[-1]["image_count_sent"],
            "receipt": stage_call_evidence[-1]["receipt_image_count"],
        },
        "report_id": report.id,
        "report_status": report.status,
        "ai_stages": stage_call_evidence,
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
    is_full_chain = args.task_type == FULL_CHAIN_HARNESS_TASK_TYPE
    runtime_task_type = (
        FULL_CHAIN_RUNTIME_TASK_TYPE if is_full_chain else args.task_type
    )
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
            require(
                isinstance(required_headers, dict), "Image upload headers are invalid"
            )
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
                    "trace_id": (f"image-trace-{run_id}-{source_image['sequence_no']}"),
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
        isinstance(current_series, list) and len(current_series) == len(runtime_series),
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
    require(
        isinstance(revision_id, str) and bool(revision_id),
        "Study revision ID is missing",
    )

    quality_task: dict[str, Any] | None = None
    quality_snapshot_evidence: dict[str, Any] = {}
    if is_full_chain:
        created_quality_task = client.call(
            "POST",
            "/tasks",
            payload={
                "study_id": study["id"],
                "study_revision_id": revision_id,
                "request_id": f"quality-task-request-{run_id}",
                "task_type": "xray_quality_control",
                "species": case["species"],
                "trace_id": f"quality-task-trace-{run_id}",
            },
        )
        require(
            isinstance(created_quality_task, dict),
            "Quality Task create response is invalid",
        )
        quality_task = wait_for_task(client, created_quality_task["id"])
        require(
            quality_task.get("task_type") == "xray_quality_control"
            and quality_task.get("finished_at") is not None
            and quality_task.get("current_report_id") is None
            and quality_task.get("ai_medical_status") == "not_produced",
            "Quality Task completion boundary drifted",
        )
        quality_snapshot_evidence = validate_snapshot(
            quality_task,
            study=finalized_study,
            series=current_series,
            images=images,
            clinical_context=None,
            species=case["species"],
            expected_config_key=None,
            expected_prompt_sha256=None,
        )
        validate_no_reports(client, task=quality_task)

    task_payload: dict[str, Any] = {
        "study_id": study["id"],
        "study_revision_id": revision_id,
        "request_id": f"task-request-{run_id}",
        "task_type": runtime_task_type,
        "species": case["species"],
        "trace_id": f"task-trace-{run_id}",
    }
    if quality_task is not None:
        task_payload["quality_review_task_id"] = quality_task["id"]
    if clinical_context is not None:
        task_payload["clinical_context"] = clinical_context
    created_task = client.call("POST", "/tasks", payload=task_payload)
    require(isinstance(created_task, dict), "Task create response is invalid")
    task = wait_for_task(client, created_task["id"])
    require(task.get("finished_at") is not None, "completed Task omitted finished_at")
    if runtime_task_type == "diagnose":
        require(
            isinstance(task.get("current_report_id"), str)
            and bool(task["current_report_id"]),
            "completed Task omitted current_report_id",
        )
        if is_full_chain:
            require(
                task.get("task_type") == FULL_CHAIN_RUNTIME_TASK_TYPE,
                "full-chain Runtime Task type drifted",
            )
    else:
        require(
            task.get("task_type") == "anatomy_localization",
            "Localization Task type drifted",
        )
        require(
            task.get("current_report_id") is None,
            "Localization Task unexpectedly produced a Report",
        )
        require(
            task.get("ai_medical_status") == "not_produced",
            "Localization Task medical status drifted",
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
    localization_response: dict[str, Any] | None = None
    if runtime_task_type == "diagnose":
        result_evidence = validate_reports(
            client,
            task=task,
            images=images,
            series_manifest_sha256=snapshot_evidence["series_manifest_sha256"],
        )
    else:
        result_evidence = validate_no_reports(client, task=task)
        localization_response, localization_evidence = validate_anatomy_localization(
            client,
            task=task,
            study=finalized_study,
            image_count=case["image_count"],
        )
        result_evidence.update(localization_evidence)
    receipt_evidence: dict[str, Any] = {}
    if args.verify_runtime_receipt:
        snapshot = task.get("request_snapshot_json")
        require(isinstance(snapshot, dict), "Task Snapshot is missing")
        if is_full_chain:
            require(quality_task is not None, "Quality Task is missing")
            quality_snapshot = quality_task.get("request_snapshot_json")
            require(
                isinstance(quality_snapshot, dict),
                "Quality Task Snapshot is missing",
            )
            receipt_evidence = asyncio.run(
                _read_full_chain_runtime_receipt(
                    quality_task_id=quality_task["id"],
                    diagnose_task_id=task["id"],
                    image_count=case["image_count"],
                    quality_snapshot=quality_snapshot,
                    diagnose_snapshot=snapshot,
                )
            )
        else:
            receipt_evidence = asyncio.run(
                _read_runtime_receipt(
                    task_id=task["id"],
                    task_type=args.task_type,
                    image_count=case["image_count"],
                    snapshot=snapshot,
                    localization_response=localization_response,
                )
            )

    evidence = {
        "qualification_status": "PASS",
        "run": run_number,
        "task_type": args.task_type,
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
        "quality_task_id": quality_task["id"] if quality_task is not None else None,
        "quality_config_key": quality_snapshot_evidence.get("config_key"),
        **snapshot_evidence,
        **result_evidence,
        **receipt_evidence,
    }
    if is_full_chain:
        print(
            f"[{run_number}/{args.repeat}] completed full-chain "
            f"quality_task={quality_task['id']} diagnose_task={task['id']} "
            f"report={result_evidence['report_id']}"
        )
    elif args.task_type == "diagnose":
        print(
            f"[{run_number}/{args.repeat}] completed task={task['id']} "
            f"report={result_evidence['report_id']}"
        )
    else:
        print(
            f"[{run_number}/{args.repeat}] completed localization "
            f"task={task['id']} call={result_evidence['ai_call_id']}"
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
