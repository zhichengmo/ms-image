#!/usr/bin/env python3
"""Run repeatable local XRay engineering E2E checks via the public Runtime API.

This tool verifies public Image, Study, Task and Report contracts. It does not
query the database, infer medical facts, or print credentials, signed URLs,
clinical text, Provider responses or report content.
"""

from __future__ import annotations

import argparse
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the public ms-image XRay engineering E2E one or more times."
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--species", required=True, choices=("cat", "dog"))
    parser.add_argument("--projection", default="UNKNOWN", type=non_empty_projection)
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
    args = parser.parse_args(argv)

    args.api_base = args.api_base.strip().rstrip("/")
    if not args.api_base:
        parser.error("--api-base must not be empty")
    args.image = args.image.expanduser().resolve()
    if not args.image.is_file():
        parser.error("--image must point to an existing file")
    if args.clinical_context_mode == "none" and args.context_recorded_at is not None:
        parser.error("--context-recorded-at requires synthetic context mode")
    if (args.expected_config_key is None) != (
        args.expected_prompt_sha256 is None
    ):
        parser.error(
            "--expected-config-key and --expected-prompt-sha256 must be supplied together"
        )
    try:
        image_media_type(args.image)
    except E2EError as exc:
        parser.error(str(exc))
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
    series: dict[str, Any],
    image: dict[str, Any],
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
        isinstance(frozen_series, list) and len(frozen_series) == 1,
        "D1 series snapshot is invalid",
    )
    frozen = frozen_series[0]
    require(isinstance(frozen, dict), "D1 series snapshot item is invalid")
    require(frozen.get("series_id") == series.get("id"), "D1 series ID drifted")
    require(frozen.get("series_key") == series.get("series_key"), "D1 series key drifted")
    require(frozen.get("series_no") == series.get("series_no"), "D1 series number drifted")
    require(
        frozen.get("manifest_contract_version") == SERIES_MANIFEST_VERSION,
        "D1 series manifest version drifted",
    )
    require(frozen.get("actual_image_count") == 1, "D1 image count is not one")
    manifest_sha = require_sha256(
        frozen.get("manifest_sha256"), "D1 series manifest SHA256 is invalid"
    )
    require(
        manifest_sha == series.get("manifest_sha256"),
        "D1 series manifest SHA256 drifted",
    )
    ordered_images = frozen.get("ordered_images")
    require(
        isinstance(ordered_images, list) and len(ordered_images) == 1,
        "D1 ordered image snapshot is invalid",
    )
    require(
        canonical_sha256(ordered_images) == manifest_sha,
        "D1 ordered image manifest does not reproduce its SHA256",
    )
    frozen_image = ordered_images[0]
    require(isinstance(frozen_image, dict), "D1 ordered image item is invalid")
    expected_image_facts = {
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
    require(frozen_image == expected_image_facts, "D1 frozen per-image facts drifted")

    study_manifest_items = [
        {
            "series_id": frozen.get("series_id"),
            "series_key": frozen.get("series_key"),
            "series_no": frozen.get("series_no"),
            "actual_image_count": frozen.get("actual_image_count"),
            "manifest_sha256": frozen.get("manifest_sha256"),
        }
    ]
    require(
        canonical_sha256(study_manifest_items)
        == snapshot.get("resolved_manifest_sha256"),
        "D1 Study manifest does not reproduce its SHA256",
    )
    return {
        "context_sha256": expected_context_sha,
        "series_manifest_sha256": manifest_sha,
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
    image_id: str,
    series_id: str,
    projection: str,
    manifest_sha256: str,
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
        require(source_ref.get("image_id") == image_id, "Report source image ID drifted")
        require(source_ref.get("series_id") == series_id, "Report source series ID drifted")
        require(source_ref.get("projection") == projection, "Report source projection drifted")
        require(
            source_ref.get("manifest_sha256") == manifest_sha256,
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


def run_once(
    client: RuntimeClient,
    *,
    args: argparse.Namespace,
    clinical_context: dict[str, Any] | None,
    content: bytes,
    image_sha256: str,
    file_format: str,
    content_type: str,
    run_number: int,
) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    recorded_now = utc_iso(datetime.now(timezone.utc))
    print(f"[{run_number}/{args.repeat}] starting new public API chain")

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
        "expected_image_count": 1,
        "identity_status": "confirmed",
        "acquired_at": recorded_now,
    }
    if args.body_part is not None:
        study_payload["body_part"] = args.body_part
    study = client.call("POST", "/studies", payload=study_payload)
    require(isinstance(study, dict), "Study response is invalid")

    series = client.call(
        "POST",
        "/series",
        payload={
            "study_id": study["id"],
            "series_key": f"local-e2e-{run_id}",
            "series_no": 1,
            "metadata_schema_version": "imaging.metadata.v1",
            "expected_image_count": 1,
            "acquired_at": recorded_now,
        },
    )
    require(isinstance(series, dict), "Series response is invalid")

    ticket = client.call(
        "POST",
        "/images/prepare-upload",
        payload={
            "series_id": series["id"],
            "logical_image_key": f"image-{run_id}",
            "sequence_no": 1,
            "image_role": "original",
            "image_kind": "instance",
            "metadata_schema_version": "imaging.metadata.v1",
            "file_format": file_format,
            "expected_sha256": image_sha256,
            "expected_size_bytes": len(content),
            "declared_content_type": content_type,
            "projection": args.projection,
        },
    )
    require(isinstance(ticket, dict), "Image upload ticket is invalid")
    ticket_image = ticket.get("image")
    require(isinstance(ticket_image, dict), "Image upload ticket omitted image")
    require(isinstance(ticket.get("signed_url"), str), "Image upload ticket omitted URL")
    required_headers = ticket.get("required_headers")
    require(isinstance(required_headers, dict), "Image upload headers are invalid")
    try:
        upload = httpx.put(
            ticket["signed_url"],
            content=content,
            headers=required_headers,
            timeout=60,
        )
    except httpx.RequestError as exc:
        raise E2EError("object upload transport failed") from exc
    require(upload.status_code < 400, f"object upload returned HTTP {upload.status_code}")

    completed_image = client.call(
        "POST",
        "/images/complete-upload",
        payload={
            "id": ticket_image["id"],
            "expected_state_version": ticket_image["state_version"],
            "generation": ticket["generation"],
            "trace_id": f"image-trace-{run_id}",
        },
    )
    require(isinstance(completed_image, dict), "complete-upload response is invalid")
    image = wait_for_image(client, ticket_image["id"])
    validate_image(
        image,
        image_id=ticket_image["id"],
        series_id=series["id"],
        projection=args.projection,
        image_sha256=image_sha256,
        image_size=len(content),
        content_type=content_type,
    )

    study_detail = client.call("GET", "/studies", params={"id": study["id"]})
    require(isinstance(study_detail, dict), "Study detail response is invalid")
    current_study = study_detail.get("study")
    current_series = study_detail.get("series")
    require(isinstance(current_study, dict), "Study detail omitted Study")
    require(
        isinstance(current_series, list) and len(current_series) == 1,
        "Study detail series contract is invalid",
    )
    current_series_item = current_series[0]
    require(isinstance(current_series_item, dict), "Study detail series item is invalid")
    require(current_series_item.get("id") == series["id"], "Study series ID drifted")
    require(current_series_item.get("status") == "ready", "Series is not ready")
    require(current_series_item.get("actual_image_count") == 1, "Series image count drifted")
    require_sha256(
        current_series_item.get("manifest_sha256"), "Series manifest SHA256 is invalid"
    )

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
        "species": args.species,
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
        series=current_series_item,
        image=image,
        clinical_context=clinical_context,
        species=args.species,
        expected_config_key=args.expected_config_key,
        expected_prompt_sha256=args.expected_prompt_sha256,
    )
    report_evidence = validate_reports(
        client,
        task=task,
        image_id=image["id"],
        series_id=series["id"],
        projection=args.projection,
        manifest_sha256=snapshot_evidence["series_manifest_sha256"],
    )

    evidence = {
        "run": run_number,
        "session_id": session["id"],
        "study_id": study["id"],
        "revision_id": revision_id,
        "series_id": series["id"],
        "image_id": image["id"],
        "image_status": image["status"],
        "image_sha256": image_sha256,
        "task_id": task["id"],
        "task_status": task["execution_status"],
        "medical_status": task["ai_medical_status"],
        **snapshot_evidence,
        **report_evidence,
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    clinical_context = build_clinical_context(args)
    try:
        content = args.image.read_bytes()
    except OSError as exc:
        raise E2EError("image file could not be read") from exc
    require(bool(content), "image file is empty")
    image_sha256 = hashlib.sha256(content).hexdigest()
    file_format, content_type = image_media_type(args.image)
    token = issue_dev_token()
    client = RuntimeClient(api_base=args.api_base, token=token)
    evidence: list[dict[str, Any]] = []
    try:
        for run_number in range(1, args.repeat + 1):
            evidence.append(
                run_once(
                    client,
                    args=args,
                    clinical_context=clinical_context,
                    content=content,
                    image_sha256=image_sha256,
                    file_format=file_format,
                    content_type=content_type,
                    run_number=run_number,
                )
            )
        validate_batch(evidence)
    finally:
        client.close()

    printable_evidence = []
    for item in evidence:
        printable = dict(item)
        printable.pop("config_fingerprint", None)
        printable_evidence.append(printable)
    print("E2E_COMPLETE")
    print(json.dumps(printable_evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except E2EError as exc:
        print(f"E2E_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
