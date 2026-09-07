import type {
  AnatomyLocalizationResponse,
  AnatomyLocalizationTaskSummary,
  ApiEnvelope,
  ImageResponse,
  ImageUploadTicket,
  LegendResponse,
  PageEnvelope,
  PrepareViewResponse,
  QualityReviewResponse,
  ReportResponse,
  SeriesResponse,
  SessionResponse,
  Species,
  StudyDetailResponse,
  StudyResponse,
  TaskResponse,
} from "../types/runtime";

interface LegacyErrorBody {
  code?: number | string;
  message?: string;
  detail?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: number | string | null;
  readonly details: unknown;

  constructor(
    message: string,
    status: number,
    errorCode: number | string | null = null,
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

function normalizeBaseUrl(baseUrl: string): string {
  const normalized = baseUrl.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(normalized)) {
    throw new ApiError("Runtime API 地址必须以 http:// 或 https:// 开头", 0);
  }
  return normalized;
}

function encodeBasicCredentials(username: string, password: string): string {
  const bytes = new TextEncoder().encode(`${username}:${password}`);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function resolveUploadUrl(signedUrl: string): string {
  const proxyTarget = import.meta.env.VITE_DEV_OSS_UPLOAD_PROXY_TARGET?.trim();
  if (!import.meta.env.DEV || !proxyTarget) return signedUrl;

  let signed: URL;
  let target: URL;
  try {
    signed = new URL(signedUrl);
    target = new URL(proxyTarget);
  } catch {
    throw new ApiError("对象存储上传地址无效", 0);
  }
  if (signed.origin !== target.origin) {
    throw new ApiError("上传票据与本地 OSS 代理目标不一致", 0);
  }
  return `/__ms_image_oss_upload${signed.pathname}${signed.search}`;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    return text ? { message: text } : null;
  }
  return response.json();
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const candidate = body as LegacyErrorBody & Partial<ApiEnvelope<unknown>>;
    if (typeof candidate.message === "string" && candidate.message.trim()) {
      return candidate.message;
    }
    if (Array.isArray(candidate.detail)) {
      return candidate.detail
        .map((entry) => {
          if (!entry || typeof entry !== "object") return String(entry);
          const record = entry as Record<string, unknown>;
          return typeof record.msg === "string" ? record.msg : JSON.stringify(record);
        })
        .join("；");
    }
  }
  return fallback;
}

export function describeApiError(error: unknown): string {
  if (error instanceof ApiError) {
    const code = error.errorCode == null ? "" : `（${String(error.errorCode)}）`;
    if (error.status === 401) return `Basic Auth 凭证无效或服务尚未启用 Basic Auth${code}。`;
    if (error.status === 403) return `当前账号缺少影像业务权限${code}。`;
    if (error.status === 404 || error.errorCode === 4041) {
      return `资源不存在或无权访问${code}。`;
    }
    if (error.errorCode === 4091) return "幂等键与原请求内容冲突，请新建检查。";
    if (error.errorCode === 4092) return "资源状态已变化，请刷新后重试。";
    if (error.status === 422) return `请求字段未通过校验${code}：${error.message}`;
    if (error.errorCode === 5031) return "数据库暂不可用，请稍后重试。";
    if (error.errorCode === 5032) return "对象存储暂不可用，请稍后重试。";
    return `${error.message}${code}`;
  }
  return error instanceof Error ? error.message : "发生未知错误";
}

export class RuntimeApi {
  private readonly baseUrl: string;
  private readonly authorization: string;

  constructor(baseUrl: string, username: string, password: string) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    const normalizedUsername = username.trim();
    if (!normalizedUsername || !password) {
      throw new ApiError("请输入 Basic Auth 用户名和密码", 0);
    }
    if (normalizedUsername.includes(":")) {
      throw new ApiError("Basic Auth 用户名不能包含冒号", 0);
    }
    this.authorization = `Basic ${encodeBasicCredentials(normalizedUsername, password)}`;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    allowNull = false,
  ): Promise<T | null> {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("Authorization", this.authorization);

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, { ...options, headers });
    } catch (error) {
      throw new ApiError(
        error instanceof Error ? error.message : "无法连接 Runtime API",
        0,
      );
    }

    const body = await parseResponse(response);
    const envelope = body as Partial<ApiEnvelope<T>> & LegacyErrorBody;
    const wrapperFailed = envelope?.success === false;
    const legacyFailed =
      envelope?.success === undefined &&
      envelope?.code !== undefined &&
      Number(envelope.code) !== 0;

    if (!response.ok || wrapperFailed || legacyFailed) {
      throw new ApiError(
        errorMessage(body, `请求失败（HTTP ${response.status}）`),
        response.status,
        envelope?.error_code ?? envelope?.code ?? null,
        envelope?.detail ?? body,
      );
    }

    if (envelope?.success === true && "data" in envelope) {
      if (envelope.data == null && !allowNull) {
        throw new ApiError("服务返回了空数据", response.status);
      }
      return (envelope.data ?? null) as T | null;
    }

    throw new ApiError("服务响应格式不符合 Runtime 合同", response.status, null, body);
  }

  private post<T>(path: string, payload: unknown, allowNull = false): Promise<T | null> {
    return this.request<T>(
      path,
      { method: "POST", body: JSON.stringify(payload) },
      allowNull,
    );
  }

  async readiness(): Promise<Record<string, unknown>> {
    return (await this.request<Record<string, unknown>>("/readiness"))!;
  }

  async verifyAuthentication(): Promise<void> {
    try {
      await this.request<TaskResponse>("/tasks?id=__basic_auth_probe__");
    } catch (error) {
      // A missing probe resource proves the request passed the authentication
      // boundary without creating or changing server-side data.
      if (error instanceof ApiError && error.status === 404) return;
      throw error;
    }
  }

  async createSession(input: {
    sourceSystem: string;
    sourceSessionId: string;
    sourceMedicalRecordId: string;
    subjectId: string;
    requestId: string;
    startedAt: string;
  }): Promise<SessionResponse> {
    return (await this.post<SessionResponse>("/sessions", {
      source_system: input.sourceSystem,
      source_session_id: input.sourceSessionId,
      source_medical_record_id: input.sourceMedicalRecordId,
      subject_id: input.subjectId,
      request_id: input.requestId,
      started_at: input.startedAt,
    }))!;
  }

  async createStudy(input: {
    sessionId: string;
    sourceStudyId: string;
    imageCount: number;
  }): Promise<StudyResponse> {
    return (await this.post<StudyResponse>("/studies", {
      session_id: input.sessionId,
      source_study_id: input.sourceStudyId,
      modality_type: "xray",
      metadata_schema_version: "xray-study.v1",
      expected_image_count: input.imageCount,
      completeness_attested_by: "ms-image-frontend",
      identity_status: "confirmed",
      technical_metadata: { source: "ms-image-frontend" },
    }))!;
  }

  async createSeries(input: {
    studyId: string;
    seriesKey: string;
    imageCount: number;
  }): Promise<SeriesResponse> {
    return (await this.post<SeriesResponse>("/series", {
      study_id: input.studyId,
      series_key: input.seriesKey,
      series_no: 1,
      metadata_schema_version: "xray-series.v1",
      expected_image_count: input.imageCount,
      technical_metadata: { source: "ms-image-frontend" },
    }))!;
  }

  async getStudy(studyId: string): Promise<StudyDetailResponse> {
    const data = (await this.request<StudyDetailResponse | StudyResponse>(
      `/studies?id=${encodeURIComponent(studyId)}`,
    ))!;
    if ("study" in data) return data;
    return { study: data, series: [] };
  }

  async finalizeStudy(input: {
    studyId: string;
    stateVersion: number;
    revisionId: string;
  }): Promise<StudyResponse> {
    return (await this.post<StudyResponse>("/studies/finalize", {
      id: input.studyId,
      expected_state_version: input.stateVersion,
      current_revision_id: input.revisionId,
    }))!;
  }

  async prepareUpload(input: {
    seriesId: string;
    logicalImageKey: string;
    sequenceNo: number;
    fileFormat: string;
    sha256: string;
    sizeBytes: number;
    contentType: string;
    projection: string;
  }): Promise<ImageUploadTicket> {
    return (await this.post<ImageUploadTicket>("/images/prepare-upload", {
      series_id: input.seriesId,
      logical_image_key: input.logicalImageKey,
      sequence_no: input.sequenceNo,
      image_role: "original",
      image_kind: "instance",
      metadata_schema_version: "xray-image.v1",
      file_format: input.fileFormat,
      expected_sha256: input.sha256,
      expected_size_bytes: input.sizeBytes,
      declared_content_type: input.contentType,
      projection: input.projection,
      technical_metadata: { source: "ms-image-frontend" },
    }))!;
  }

  async uploadObject(
    signedUrl: string,
    file: File,
    contentType: string,
    requiredHeaders: Record<string, string>,
  ): Promise<void> {
    const headers = new Headers(requiredHeaders);
    if (!headers.has("Content-Type")) headers.set("Content-Type", contentType);
    const response = await fetch(resolveUploadUrl(signedUrl), {
      method: "PUT",
      headers,
      body: file,
    });
    if (!response.ok) {
      throw new ApiError("影像上传到对象存储失败", response.status);
    }
  }

  async completeUpload(input: {
    imageId: string;
    stateVersion: number;
    generation: number;
    traceId: string;
  }): Promise<ImageResponse> {
    return (await this.post<ImageResponse>("/images/complete-upload", {
      id: input.imageId,
      expected_state_version: input.stateVersion,
      generation: input.generation,
      trace_id: input.traceId,
    }))!;
  }

  async getImage(imageId: string): Promise<ImageResponse> {
    return (await this.request<ImageResponse>(
      `/images?id=${encodeURIComponent(imageId)}`,
    ))!;
  }

  async listImages(seriesId: string): Promise<ImageResponse[]> {
    const path = `/images/page?series_id=${encodeURIComponent(seriesId)}&current_only=true&page=1&page_size=20`;
    const response = await this.request<ImageResponse[]>(path);
    return response ?? [];
  }

  async createQualityReview(input: {
    studyId: string;
    revisionId: string;
    requestId: string;
    species: Species;
    traceId: string;
  }): Promise<TaskResponse> {
    return (await this.post<TaskResponse>("/xray-quality-reviews", {
      study_id: input.studyId,
      study_revision_id: input.revisionId,
      request_id: input.requestId,
      species: input.species,
      trace_id: input.traceId,
    }))!;
  }

  async getQualityReview(taskId: string): Promise<QualityReviewResponse> {
    return (await this.request<QualityReviewResponse>(
      `/xray-quality-reviews?task_id=${encodeURIComponent(taskId)}`,
    ))!;
  }

  async createDiagnoseTask(input: {
    studyId: string;
    revisionId: string;
    requestId: string;
    species: Species;
    qualityTaskId: string;
    chiefComplaint: string;
    studyReason: string;
    recordedAt: string;
    traceId: string;
  }): Promise<TaskResponse> {
    return (await this.post<TaskResponse>("/tasks", {
      study_id: input.studyId,
      study_revision_id: input.revisionId,
      request_id: input.requestId,
      task_type: "diagnose",
      species: input.species,
      quality_review_task_id: input.qualityTaskId,
      clinical_context: {
        contract_version: "xray-clinical-context.v1",
        source: {
          system: "ms-image-frontend",
          recorded_at: input.recordedAt,
          temporal_scope: "available_at_request",
        },
        chief_complaint: input.chiefComplaint || "未提供主诉",
        study_reason: input.studyReason,
      },
      trace_id: input.traceId,
    }))!;
  }

  async createLocalizationTask(input: {
    studyId: string;
    revisionId: string;
    requestId: string;
    species: Species;
    diagnoseTaskId: string;
    traceId: string;
  }): Promise<TaskResponse> {
    return (await this.post<TaskResponse>("/tasks", {
      study_id: input.studyId,
      study_revision_id: input.revisionId,
      request_id: input.requestId,
      task_type: "anatomy_localization",
      species: input.species,
      source_task_id: input.diagnoseTaskId,
      trace_id: input.traceId,
    }))!;
  }

  async getTask(taskId: string): Promise<TaskResponse> {
    return (await this.request<TaskResponse>(
      `/tasks?id=${encodeURIComponent(taskId)}`,
    ))!;
  }

  async cancelTask(taskId: string, stateVersion: number): Promise<TaskResponse> {
    return (await this.post<TaskResponse>("/tasks/cancel", {
      id: taskId,
      expected_state_version: stateVersion,
      reason: "前端用户主动取消",
    }))!;
  }

  async getCurrentReport(taskId: string): Promise<ReportResponse | null> {
    return this.request<ReportResponse>(
      `/reports/current?task_id=${encodeURIComponent(taskId)}`,
      {},
      true,
    );
  }

  async getReportHistory(taskId: string): Promise<ReportResponse[]> {
    return (
      (await this.request<ReportResponse[]>(
        `/reports/history?task_id=${encodeURIComponent(taskId)}`,
      )) ?? []
    );
  }

  async getReport(reportId: string): Promise<ReportResponse> {
    return (await this.request<ReportResponse>(
      `/reports?id=${encodeURIComponent(reportId)}`,
    ))!;
  }

  async getCurrentLocalization(
    diagnoseTaskId: string,
  ): Promise<AnatomyLocalizationTaskSummary | null> {
    return this.request<AnatomyLocalizationTaskSummary>(
      `/anatomy-localizations/current?source_task_id=${encodeURIComponent(diagnoseTaskId)}`,
      {},
      true,
    );
  }

  async getLocalizationHistory(
    diagnoseTaskId: string,
  ): Promise<{ items: AnatomyLocalizationTaskSummary[]; page: PageEnvelope<AnatomyLocalizationTaskSummary> | null }> {
    const path = `/anatomy-localizations/history?source_task_id=${encodeURIComponent(diagnoseTaskId)}&page=1&page_size=20`;
    const headers = new Headers({ Accept: "application/json" });
    headers.set("Authorization", this.authorization);
    const response = await fetch(`${this.baseUrl}${path}`, { headers });
    const body = (await parseResponse(response)) as PageEnvelope<AnatomyLocalizationTaskSummary>;
    if (!response.ok || body.success === false) {
      throw new ApiError(
        errorMessage(body, "定位历史查询失败"),
        response.status,
        body.error_code ?? null,
        body,
      );
    }
    return { items: body.data ?? [], page: body };
  }

  async getLocalizationResult(taskId: string): Promise<AnatomyLocalizationResponse> {
    return (await this.request<AnatomyLocalizationResponse>(
      `/anatomy-localizations?task_id=${encodeURIComponent(taskId)}`,
    ))!;
  }

  async prepareLocalizationView(
    taskId: string,
    imageIds: string[] | null = null,
  ): Promise<PrepareViewResponse> {
    return (await this.post<PrepareViewResponse>(
      "/anatomy-localizations/prepare-view",
      { task_id: taskId, image_ids: imageIds },
    ))!;
  }

  async getLocalizationLegend(): Promise<LegendResponse> {
    return (await this.request<LegendResponse>(
      "/anatomy-localizations/legend?label_contract_version=xray-anatomy-labels.v1&locale=zh-CN",
    ))!;
  }
}
