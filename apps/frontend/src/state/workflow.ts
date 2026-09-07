import type { Species, TaskResponse } from "../types/runtime";

export type WorkspaceView = "workflow" | "report" | "localization";

export interface PersistedImageState {
  sequenceNo: number;
  name: string;
  projection: string;
  imageId: string | null;
  stateVersion: number | null;
  status: string;
  errorCode: string | null;
}

export interface WorkflowState {
  baseUrl: string;
  runId: string;
  subjectId: string;
  caseKey: string;
  species: Species;
  chiefComplaint: string;
  studyReason: string;
  sessionStartedAt: string | null;
  sessionId: string | null;
  sessionStateVersion: number | null;
  studyId: string | null;
  studyRevisionId: string | null;
  studyStateVersion: number | null;
  studyStatus: string | null;
  seriesId: string | null;
  images: PersistedImageState[];
  qualityTask: TaskResponse | null;
  diagnoseTask: TaskResponse | null;
  localizationTask: TaskResponse | null;
  reportId: string | null;
  activeView: WorkspaceView;
}

const STORAGE_KEY = "ms-image.xray.workflow.v1";

export function makeRunId(): string {
  return `${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
}

export function createInitialWorkflow(): WorkflowState {
  return {
    baseUrl:
      import.meta.env.VITE_RUNTIME_API_BASE_URL ??
      "http://127.0.0.1:8010/api/v1",
    runId: makeRunId(),
    subjectId: "",
    caseKey: "",
    species: "cat",
    chiefComplaint: "",
    studyReason: "X-Ray 检查",
    sessionStartedAt: null,
    sessionId: null,
    sessionStateVersion: null,
    studyId: null,
    studyRevisionId: null,
    studyStateVersion: null,
    studyStatus: null,
    seriesId: null,
    images: [],
    qualityTask: null,
    diagnoseTask: null,
    localizationTask: null,
    reportId: null,
    activeView: "workflow",
  };
}

export function loadWorkflow(): WorkflowState {
  const fallback = createInitialWorkflow();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<WorkflowState>;
    return {
      ...fallback,
      baseUrl: typeof parsed.baseUrl === "string" ? parsed.baseUrl : fallback.baseUrl,
      runId: typeof parsed.runId === "string" ? parsed.runId : fallback.runId,
      subjectId: typeof parsed.subjectId === "string" ? parsed.subjectId : "",
      caseKey: typeof parsed.caseKey === "string" ? parsed.caseKey : "",
      species: parsed.species === "dog" ? "dog" : "cat",
      sessionStartedAt: stringOrNull(parsed.sessionStartedAt),
      sessionId: stringOrNull(parsed.sessionId),
      sessionStateVersion: numberOrNull(parsed.sessionStateVersion),
      studyId: stringOrNull(parsed.studyId),
      studyRevisionId: stringOrNull(parsed.studyRevisionId),
      studyStateVersion: numberOrNull(parsed.studyStateVersion),
      studyStatus: stringOrNull(parsed.studyStatus),
      seriesId: stringOrNull(parsed.seriesId),
      images: Array.isArray(parsed.images)
        ? parsed.images.map(sanitizeImage).filter((image): image is PersistedImageState => image !== null)
        : [],
      qualityTask: sanitizeTask(parsed.qualityTask),
      diagnoseTask: sanitizeTask(parsed.diagnoseTask),
      localizationTask: sanitizeTask(parsed.localizationTask),
      reportId: stringOrNull(parsed.reportId),
      activeView: ["workflow", "report", "localization"].includes(parsed.activeView ?? "")
        ? parsed.activeView!
        : "workflow",
    };
  } catch {
    return fallback;
  }
}

export function persistWorkflow(state: WorkflowState): void {
  // Persist only operational identifiers and explicitly declared task fields.
  // Free-text clinical context, server snapshots and undeclared response fields
  // remain in memory and are discarded on refresh.
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      baseUrl: state.baseUrl,
      runId: state.runId,
      subjectId: state.subjectId,
      caseKey: state.caseKey,
      species: state.species,
      sessionStartedAt: state.sessionStartedAt,
      sessionId: state.sessionId,
      sessionStateVersion: state.sessionStateVersion,
      studyId: state.studyId,
      studyRevisionId: state.studyRevisionId,
      studyStateVersion: state.studyStateVersion,
      studyStatus: state.studyStatus,
      seriesId: state.seriesId,
      images: state.images.map((image) => ({
        sequenceNo: image.sequenceNo,
        name: image.name,
        projection: image.projection,
        imageId: image.imageId,
        stateVersion: image.stateVersion,
        status: image.status,
        errorCode: image.errorCode,
      })),
      qualityTask: sanitizeTask(state.qualityTask),
      diagnoseTask: sanitizeTask(state.diagnoseTask),
      localizationTask: sanitizeTask(state.localizationTask),
      reportId: state.reportId,
      activeView: state.activeView,
    }),
  );
}

export function resetWorkflow(baseUrl: string): WorkflowState {
  const next = createInitialWorkflow();
  next.baseUrl = baseUrl;
  persistWorkflow(next);
  return next;
}

export function isTaskActive(task: TaskResponse | null): boolean {
  return Boolean(
    task &&
      ["pending", "queued", "running", "retry_wait"].includes(
        task.execution_status,
      ),
  );
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sanitizeImage(value: unknown): PersistedImageState | null {
  if (!value || typeof value !== "object") return null;
  const image = value as Partial<PersistedImageState>;
  if (
    typeof image.sequenceNo !== "number" ||
    typeof image.name !== "string" ||
    typeof image.projection !== "string" ||
    typeof image.status !== "string"
  ) return null;
  return {
    sequenceNo: image.sequenceNo,
    name: image.name,
    projection: image.projection,
    imageId: stringOrNull(image.imageId),
    stateVersion: numberOrNull(image.stateVersion),
    status: image.status,
    errorCode: stringOrNull(image.errorCode),
  };
}

function sanitizeTask(task: TaskResponse | null | undefined): TaskResponse | null {
  if (!task || typeof task !== "object" || typeof task.id !== "string") return null;
  const anatomy = task.anatomy_localization;
  const safeAnatomy = anatomy && typeof anatomy.task_id === "string"
    ? {
        task_id: anatomy.task_id,
        source_task_id: anatomy.source_task_id,
        study_id: anatomy.study_id,
        study_revision_id: anatomy.study_revision_id,
        request_id: anatomy.request_id,
        execution_status: anatomy.execution_status,
        result_available: anatomy.result_available,
        state_version: anatomy.state_version,
        error_code: anatomy.error_code,
        next_retry_at: anatomy.next_retry_at,
        started_at: anatomy.started_at,
        finished_at: anatomy.finished_at,
        created_at: anatomy.created_at,
        updated_at: anatomy.updated_at,
      }
    : null;
  return {
    id: task.id,
    study_id: task.study_id,
    source_task_id: task.source_task_id,
    request_id: task.request_id,
    task_type: task.task_type,
    study_revision_id: task.study_revision_id,
    execution_status: task.execution_status,
    ai_medical_status: task.ai_medical_status,
    state_version: task.state_version,
    current_report_id: task.current_report_id,
    anatomy_localization: safeAnatomy,
    error_code: task.error_code,
    next_retry_at: task.next_retry_at,
    cancel_requested_at: task.cancel_requested_at,
    started_at: task.started_at,
    finished_at: task.finished_at,
    created_at: task.created_at,
    updated_at: task.updated_at,
  };
}
