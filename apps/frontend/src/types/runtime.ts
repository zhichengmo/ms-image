export type Species = "cat" | "dog";
export type TaskExecutionStatus =
  | "pending"
  | "queued"
  | "running"
  | "retry_wait"
  | "completed"
  | "failed"
  | "cancelled"
  | "dead_letter";

export interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  data: T | null;
  error_code: number;
}

export interface PageInfo {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface PageEnvelope<T> extends ApiEnvelope<T[]> {
  page_info: PageInfo;
}

export interface SessionResponse {
  id: string;
  status: string;
  state_version: number;
  created_at: string;
  updated_at: string;
}

export interface StudyResponse {
  id: string;
  session_id: string;
  revision_id: string;
  expected_image_count: number | null;
  completeness_status: string;
  identity_status: string;
  status: string;
  state_version: number;
  created_at: string;
  updated_at: string;
}

export interface SeriesResponse {
  id: string;
  study_id: string;
  status: string;
  state_version: number;
  expected_image_count: number | null;
  actual_image_count: number;
}

export interface StudyDetailResponse {
  study: StudyResponse;
  series: SeriesResponse[];
}

export interface ImageResponse {
  id: string;
  series_id: string;
  logical_image_key: string;
  sequence_no: number;
  file_format: string;
  declared_content_type: string | null;
  content_type: string | null;
  projection: string | null;
  status: string;
  state_version: number;
  validation_attempt_count: number;
  next_validation_at: string | null;
  error_code: string | null;
  verified_at: string | null;
}

export interface ImageUploadTicket {
  image: ImageResponse;
  generation: number;
  upload_mode: string;
  required_headers: Record<string, string>;
  expires_at: string;
  signed_url: string;
}

export interface AnatomyLocalizationTaskSummary {
  task_id: string;
  source_task_id: string;
  study_id: string;
  study_revision_id: string;
  request_id: string;
  execution_status: TaskExecutionStatus;
  result_available: boolean;
  state_version: number;
  error_code: string | null;
  next_retry_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskResponse {
  id: string;
  study_id: string;
  source_task_id: string | null;
  request_id: string;
  task_type: string;
  study_revision_id: string;
  execution_status: TaskExecutionStatus;
  ai_medical_status: string;
  state_version: number;
  current_report_id: string | null;
  anatomy_localization: AnatomyLocalizationTaskSummary | null;
  error_code: string | null;
  next_retry_at: string | null;
  cancel_requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QualityImageResult {
  image_id: string;
  series_id: string;
  sequence_no: number;
  declared_projection: string;
  observed_projection: string | null;
  projection_consistency: string;
  is_valid_xray: boolean;
  primary_body_part: string;
  quality_status: string;
  quality_issue_codes: string[];
}

export interface QualityReviewResponse {
  task_id: string;
  study_id: string;
  study_revision_id: string;
  output_sha256: string;
  result: {
    contract_version: "xray-image-quality.v1";
    species: Species;
    result_status: "complete" | "partial" | "unavailable";
    images: QualityImageResult[];
  };
}

export interface ReportResponse {
  id: string;
  task_id: string;
  revision_no: number;
  medical_status: string;
  content_json: Record<string, unknown>;
  content_sha256: string;
  status: "current" | "final" | "published" | "superseded" | "void" | string;
  published_at: string | null;
  voided_at: string | null;
  error_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface LocalizationOrgan {
  system: string;
  label: string;
  bbox: [number, number, number, number];
}

export interface LocalizationImageResult {
  image_id: string;
  series_id: string;
  sequence_no: number;
  projection: string;
  series_manifest_sha256: string;
  status: "localized" | "not_localized";
  reason_code:
    | "no_supported_anatomy_visible"
    | "insufficient_localization_evidence"
    | null;
  organs: LocalizationOrgan[];
}

export interface AnatomyLocalizationResponse {
  task_id: string;
  source_task_id: string | null;
  study_id: string;
  study_revision_id: string;
  output_sha256: string;
  result: {
    contract_version: "xray-anatomy-localization.v1";
    label_contract_version: "xray-anatomy-labels.v1";
    species: Species;
    result_status: "complete" | "partial" | "unavailable";
    images: LocalizationImageResult[];
  };
}

export interface ViewImage {
  image_id: string;
  series_id: string;
  sequence_no: number;
  projection: string;
  file_format: string;
  content_type: string;
  pixel_width: number | null;
  pixel_height: number | null;
  expires_at: string;
  signed_url: string;
}

export interface PrepareViewResponse {
  task_id: string;
  source_task_id: string | null;
  study_id: string;
  study_revision_id: string;
  expires_in: number;
  images: ViewImage[];
}

export interface LegendLabel {
  label: string;
  display_name: string;
  sort_order: number;
}

export interface LegendSystem {
  system: string;
  display_name: string;
  color: string;
  sort_order: number;
  labels: LegendLabel[];
}

export interface LegendResponse {
  label_contract_version: "xray-anatomy-labels.v1";
  locale: "zh-CN";
  systems: LegendSystem[];
}
