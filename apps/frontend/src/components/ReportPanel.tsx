import { useEffect, useMemo, useState } from "react";

import type {
  AnatomyLocalizationResponse,
  LegendResponse,
  PrepareViewResponse,
  ReportResponse,
  TaskResponse,
} from "../types/runtime";
import { ReportImagingPanel } from "./ReportImagingPanel";
import {
  Button,
  EmptyState,
  ErrorNotice,
  formatDateTime,
  Icon,
  LoadingState,
  StatusBadge,
} from "./ui";

interface ReportPanelProps {
  diagnoseTask: TaskResponse | null;
  localizationTask: TaskResponse | null;
  current: ReportResponse | null;
  history: ReportResponse[];
  loading: boolean;
  error: string | null;
  localizationResult: AnatomyLocalizationResponse | null;
  localizationView: PrepareViewResponse | null;
  legend: LegendResponse | null;
  localizationLoading: boolean;
  localizationError: string | null;
  onLoad: () => void;
  onSelect: (reportId: string) => void;
  onLoadLocalization: () => void;
  onRefreshLocalizationView: (imageIds?: string[] | null) => void;
}

type JsonRecord = Record<string, unknown>;

interface ReportFinding {
  id: string;
  label: string;
  description: string;
  anatomyRegion: string | null;
  laterality: string | null;
  sourceRefIds: string[];
}

interface SourceRef {
  id: string;
  imageId: string;
  projection: string | null;
}

type ParallelLaneKind = "diagnose" | "localization";

const activeTaskStatuses = new Set(["pending", "queued", "running", "retry_wait"]);

function shortId(value: string | null | undefined): string {
  if (!value) return "待创建";
  return value.length > 16 ? `${value.slice(0, 12)}…` : value;
}

function taskLaneOutcome(kind: ParallelLaneKind, task: TaskResponse | null): string {
  if (!task) return kind === "diagnose" ? "等待诊断任务" : "等待展示任务";
  if (task.execution_status === "completed") {
    return kind === "diagnose" ? "报告已生成" : "已可阅片";
  }
  if (activeTaskStatuses.has(task.execution_status)) {
    return kind === "diagnose" ? "报告生成中" : "定位处理中";
  }
  if (task.execution_status === "cancelled") return "任务已取消";
  return "任务未完成";
}

function ParallelTaskLane({
  kind,
  task,
}: {
  kind: ParallelLaneKind;
  task: TaskResponse | null;
}) {
  const failed = Boolean(task && ["failed", "dead_letter"].includes(task.execution_status));
  const moments = [
    { label: "创建", value: task?.created_at ?? null },
    { label: "开始", value: task?.started_at ?? null },
    { label: failed ? "结束" : "完成", value: task?.finished_at ?? null },
  ];
  const currentMoment = task
    ? task.finished_at
      ? -1
      : task.started_at
        ? 2
        : 1
    : 0;

  return (
    <article className={`report-parallel-lane report-parallel-lane--${kind}${failed ? " report-parallel-lane--failed" : ""}`}>
      <header>
        <span className="report-parallel-lane__icon"><Icon name={kind === "diagnose" ? "report" : "image"} /></span>
        <div>
          <small>{kind === "diagnose" ? "Diagnose · 主链" : "Localization · 展示链"}</small>
          <strong>{taskLaneOutcome(kind, task)}</strong>
        </div>
        {task ? <StatusBadge status={task.execution_status} /> : <span className="status status--muted">未创建</span>}
      </header>

      <ol className="report-parallel-lane__timeline" aria-label={`${kind === "diagnose" ? "诊断主链" : "定位展示链"}时间线`}>
        {moments.map((moment, index) => {
          const state = moment.value ? "done" : index === currentMoment ? "current" : "pending";
          return (
            <li className={`report-parallel-moment report-parallel-moment--${state}`} key={moment.label}>
              <span aria-hidden="true" />
              <small>{moment.label}</small>
              <time dateTime={moment.value ?? undefined}>{formatDateTime(moment.value)}</time>
            </li>
          );
        })}
      </ol>

      <dl className="report-parallel-lane__ids">
        <div><dt>Task ID</dt><dd title={task?.id}>{shortId(task?.id)}</dd></div>
        {kind === "localization" ? (
          <div><dt>source_task_id</dt><dd title={task?.source_task_id ?? undefined}>{shortId(task?.source_task_id)}</dd></div>
        ) : null}
      </dl>
    </article>
  );
}

function asRecord(value: unknown): JsonRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as JsonRecord
    : null;
}

function asText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

function asTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string" && item.trim()) return [item.trim()];
    const record = asRecord(item);
    if (!record) return [];
    const text = asText(record.description) ?? asText(record.label) ?? asText(record.value);
    return text ? [text] : [];
  });
}

function resolveMedicalResult(content: JsonRecord): JsonRecord {
  return asRecord(content.final_medical_result)
    ?? asRecord(content.complete_medical_result)
    ?? content;
}

function normalizeFindings(value: unknown): ReportFinding[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item, index) => {
    if (typeof item === "string" && item.trim()) {
      return [{
        id: `finding-${index + 1}`,
        label: `影像所见 ${index + 1}`,
        description: item.trim(),
        anatomyRegion: null,
        laterality: null,
        sourceRefIds: [],
      }];
    }
    const record = asRecord(item);
    if (!record) return [];
    const label = asText(record.label) ?? `影像所见 ${index + 1}`;
    return [{
      id: asText(record.finding_id) ?? `finding-${index + 1}`,
      label,
      description: asText(record.description) ?? asText(record.value) ?? label,
      anatomyRegion: asText(record.anatomy_region),
      laterality: asText(record.laterality),
      sourceRefIds: asTextList(record.source_ref_ids),
    }];
  });
}

function normalizeSourceRefs(value: unknown): SourceRef[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const record = asRecord(item);
    const id = asText(record?.source_ref_id);
    const imageId = asText(record?.image_id);
    if (!id || !imageId) return [];
    return [{ id, imageId, projection: asText(record?.projection) }];
  });
}

function medicalStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    normal: "未见明确异常",
    abnormal: "发现异常",
    review_required: "需要兽医复核",
    non_diagnostic: "影像不足以诊断",
    produced: "报告已生成",
    not_produced: "未生成医学结论",
  };
  return labels[status] ?? status;
}

function TextList({ items, empty = "暂无" }: { items: string[]; empty?: string }) {
  if (items.length === 0) return <p className="report-muted">{empty}</p>;
  return (
    <ul className="report-text-list">
      {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
    </ul>
  );
}

export function ReportPanel({
  diagnoseTask,
  localizationTask,
  current,
  history,
  loading,
  error,
  localizationResult,
  localizationView,
  legend,
  localizationLoading,
  localizationError,
  onLoad,
  onSelect,
  onLoadLocalization,
  onRefreshLocalizationView,
}: ReportPanelProps) {
  const [showRaw, setShowRaw] = useState(false);
  const [focusImageId, setFocusImageId] = useState<string | null>(null);

  useEffect(() => {
    if (diagnoseTask?.execution_status === "completed" && !current && !loading && !error) onLoad();
  }, [current, diagnoseTask?.execution_status, error, loading, onLoad]);

  useEffect(() => {
    if (
      localizationTask?.execution_status === "completed"
      && !localizationResult
      && !localizationLoading
      && !localizationError
    ) onLoadLocalization();
  }, [localizationError, localizationLoading, localizationResult, localizationTask?.execution_status, onLoadLocalization]);

  const sortedHistory = useMemo(
    () => [...history].sort((a, b) => b.revision_no - a.revision_no),
    [history],
  );

  const report = useMemo(() => {
    if (!current) return null;
    const content = current.content_json;
    const medical = resolveMedicalResult(content);
    const coverage = asRecord(medical.coverage);
    const targetedCandidate = asRecord(medical.targeted_candidate);
    return {
      schemaVersion: asText(content.result_schema_version) ?? asText(medical.result_schema_version) ?? "未声明",
      medicalStatus: asText(medical.medical_status) ?? current.medical_status,
      studySummary: asText(content.study_summary) ?? asText(medical.summary),
      technicalQuality: asText(content.technical_quality_summary) ?? asText(medical.technical_quality_summary),
      summary: asText(medical.summary) ?? asText(content.summary),
      impression: asText(medical.impression) ?? asText(content.impression),
      findings: normalizeFindings(medical.findings ?? content.findings),
      recommendations: asTextList(medical.recommendations ?? content.recommendations),
      normalBasis: asTextList(medical.normal_basis),
      assessedRegions: asTextList(coverage?.assessed_regions),
      missingViews: asTextList(coverage?.missing_or_limited_views),
      coverageStatus: asText(coverage?.status),
      familiesNotAssessed: asTextList(medical.families_not_assessed),
      limitations: asTextList(medical.limitations ?? content.limitations),
      reviewReason: asText(medical.review_reason),
      sourceRefs: normalizeSourceRefs(medical.source_refs),
      targetedCandidate: targetedCandidate ? {
        family: asText(targetedCandidate.family_key),
        focus: asText(targetedCandidate.focus_key),
        reason: asText(targetedCandidate.reason),
      } : null,
    };
  }, [current]);

  const sourceRefMap = useMemo(
    () => new Map(report?.sourceRefs.map((source) => [source.id, source]) ?? []),
    [report?.sourceRefs],
  );

  const refreshAll = () => {
    if (diagnoseTask?.execution_status === "completed") onLoad();
    if (localizationTask?.execution_status === "completed") onLoadLocalization();
  };

  const diagnoseCompleted = diagnoseTask?.execution_status === "completed";
  const localizationCompleted = localizationTask?.execution_status === "completed";
  const bothActive = Boolean(
    diagnoseTask
    && localizationTask
    && activeTaskStatuses.has(diagnoseTask.execution_status)
    && activeTaskStatuses.has(localizationTask.execution_status),
  );
  const parallelSummary = diagnoseCompleted && localizationCompleted
    ? {
        tone: "complete",
        title: "两条链路均已完成，可以交叉核对",
        detail: "报告结论与原图定位证据在同一工作台汇合，但各自保留独立 Task、状态与时间证据。",
      }
    : localizationCompleted && !diagnoseCompleted
      ? {
          tone: "review",
          title: "定位展示已就绪，诊断报告仍在生成",
          detail: "现在即可阅片；Localization 的完成不会等待或阻塞 Diagnose。",
        }
      : diagnoseCompleted && !localizationCompleted
        ? {
            tone: "review",
            title: "诊断报告已就绪，定位展示仍在生成",
            detail: "报告可先阅读；定位结果返回后会独立补入左侧阅片区。",
          }
        : bothActive
          ? {
              tone: "active",
              title: "诊断主链与定位展示链正在并行执行",
              detail: "Localization 仅在取得 Diagnose Task ID 后创建，随后两条执行链独立轮询、重叠运行。",
            }
          : {
              tone: "muted",
              title: "正在建立两条任务链",
              detail: "共同前置完成后，页面会分别呈现诊断报告与定位展示的推进状态。",
            };

  return (
    <section className="workspace-section report-workspace" aria-labelledby="report-heading">
      <div className="workspace-section__heading">
        <div>
          <span className="eyebrow">影像诊断交付</span>
          <h1 id="report-heading">宠物 X-Ray 影像诊断报告</h1>
          <p>原始影像、定位框证据与冻结报告在同一页面核对；主链和展示链保持相互独立。</p>
        </div>
        <Button disabled={!diagnoseTask && !localizationTask} onClick={refreshAll}><Icon name="refresh" />刷新全部</Button>
      </div>

      {!diagnoseTask && !localizationTask ? (
        <EmptyState icon="report" title="尚无 X-Ray 诊断任务" description="请先完成影像上传、冻结与质量审查，再创建诊断任务。" />
      ) : (
        <>
          <div className="report-evidence-boundary" aria-label="当前页面证据边界">
            <span><Icon name="check" />真实数据集影像</span>
            <span><Icon name="activity" />真实工程链路</span>
            <span><Icon name="image" />矩形标注（非像素分割）</span>
            <span><Icon name="shield" />非临床诊断</span>
          </div>

          <section className="report-parallel-flow" aria-labelledby="parallel-flow-heading">
            <div className="report-parallel-flow__origin">
              <span><Icon name="check" /></span>
              <div>
                <small>共同前置已完成</small>
                <strong id="parallel-flow-heading">Study Revision 冻结 · Quality Review 完成</strong>
              </div>
              <code title={localizationTask?.source_task_id ?? diagnoseTask?.id ?? undefined}>
                source_task_id · {shortId(localizationTask?.source_task_id ?? diagnoseTask?.id)}
              </code>
            </div>

            <div className="report-parallel-flow__lanes">
              <ParallelTaskLane kind="diagnose" task={diagnoseTask} />
              <ParallelTaskLane kind="localization" task={localizationTask} />
            </div>

            <div className={`report-parallel-flow__summary report-parallel-flow__summary--${parallelSummary.tone}`} role="status">
              <Icon name={parallelSummary.tone === "complete" ? "check" : "activity"} />
              <div><small>当前运行关系</small><strong>{parallelSummary.title}</strong><p>{parallelSummary.detail}</p></div>
            </div>
          </section>

          {sortedHistory.length > 0 ? (
            <nav className="report-version-bar" aria-label="报告版本历史">
              <span>报告版本</span>
              <div>
                {sortedHistory.map((item) => (
                  <button
                    className={item.id === current?.id ? "report-version report-version--active" : "report-version"}
                    key={item.id}
                    onClick={() => onSelect(item.id)}
                  >
                    <strong>R{item.revision_no}</strong><small>{formatDateTime(item.created_at)}</small>
                  </button>
                ))}
              </div>
            </nav>
          ) : null}

          <div className="report-clinical-layout">
            <ReportImagingPanel
              localizationTask={localizationTask}
              result={localizationResult}
              view={localizationView}
              legend={legend}
              loading={localizationLoading}
              error={localizationError}
              focusImageId={focusImageId}
              onLoad={onLoadLocalization}
              onRefreshView={onRefreshLocalizationView}
            />

            <article className="clinical-report-document">
              {loading && !current ? (
                <LoadingState label="正在读取最终诊断报告" />
              ) : error && !current ? (
                <ErrorNotice message={error} onRetry={onLoad} />
              ) : !current || !report ? (
                <div className="clinical-report-pending">
                  {diagnoseTask?.execution_status === "completed" ? <Icon name="report" /> : <span className="spinner" aria-hidden="true" />}
                  <span className="eyebrow">诊断主链</span>
                  <h2>{diagnoseTask?.execution_status === "completed" ? "报告正在归档" : "最终报告生成中"}</h2>
                  <p>{diagnoseTask?.execution_status === "completed" ? "任务已完成，但当前报告尚未返回。可刷新报告重试。" : "展示链完成后可先查看原图与定位框；最终医学结论会在诊断主链完成后独立出现。"}</p>
                  {diagnoseTask?.execution_status === "completed" ? <Button onClick={onLoad}>读取报告</Button> : null}
                </div>
              ) : (
                <>
                  <header className="clinical-report-header">
                    <div><span className="eyebrow">Final Report · Revision {current.revision_no}</span><h2>宠物 X 光影像学检查报告</h2><p>AI-assisted radiology report</p></div>
                    <div className={`medical-result-status medical-result-status--${report.medicalStatus}`}><small>医学状态</small><strong>{medicalStatusLabel(report.medicalStatus)}</strong></div>
                  </header>

                  <dl className="clinical-report-meta">
                    <div><dt>报告编号</dt><dd title={current.id}>{current.id.slice(0, 16)}</dd></div>
                    <div><dt>生成时间</dt><dd>{formatDateTime(current.created_at)}</dd></div>
                    <div><dt>报告状态</dt><dd><StatusBadge status={current.status} /></dd></div>
                    <div><dt>结构版本</dt><dd>{report.schemaVersion}</dd></div>
                  </dl>

                  <section className="report-summary-block"><span>检查摘要</span><p>{report.studySummary ?? report.summary ?? "后端未提供检查摘要。"}</p></section>

                  <section className="clinical-report-section">
                    <header><span>01</span><div><small>Technical Quality</small><h3>技术质量与可诊断性</h3></div></header>
                    <p>{report.technicalQuality ?? "后端未单独提供技术质量摘要。"}</p>
                    <div className="report-coverage-grid">
                      <div><small>覆盖状态</small><strong>{report.coverageStatus ?? "未声明"}</strong></div>
                      <div><small>已评估区域</small><strong>{report.assessedRegions.length}</strong></div>
                      <div><small>受限视图</small><strong>{report.missingViews.length}</strong></div>
                    </div>
                    {report.missingViews.length > 0 ? <TextList items={report.missingViews} /> : null}
                  </section>

                  <section className="clinical-report-section">
                    <header><span>02</span><div><small>Radiographic Findings</small><h3>影像所见</h3></div></header>
                    {report.findings.length > 0 ? (
                      <div className="report-findings">
                        {report.findings.map((finding, index) => {
                          const evidence = finding.sourceRefIds.map((id) => sourceRefMap.get(id)).filter((item): item is SourceRef => Boolean(item));
                          return (
                            <article className="report-finding" key={finding.id}>
                              <span>{String(index + 1).padStart(2, "0")}</span>
                              <div>
                                <div className="report-finding__title"><h4>{finding.label}</h4>{[finding.anatomyRegion, finding.laterality].filter(Boolean).map((tag) => <em key={tag}>{tag}</em>)}</div>
                                <p>{finding.description}</p>
                                {evidence.length > 0 ? (
                                  <div className="report-finding__evidence"><small>证据影像</small>{evidence.map((source) => <button aria-label={`在阅片区查看 ${source.projection ?? source.imageId.slice(0, 8)} 证据影像`} key={source.id} type="button" onClick={() => setFocusImageId(source.imageId)}><Icon name="eye" />{source.projection ?? source.imageId.slice(0, 8)}</button>)}</div>
                                ) : null}
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    ) : <p className="report-muted">后端未返回结构化影像所见。</p>}
                  </section>

                  {report.normalBasis.length > 0 ? (
                    <section className="clinical-report-section clinical-report-section--normal">
                      <header><span>03</span><div><small>Normal Basis</small><h3>未见异常的判断依据</h3></div></header>
                      <TextList items={report.normalBasis} />
                    </section>
                  ) : null}

                  <section className="clinical-report-section clinical-report-section--impression">
                    <header><span>{report.normalBasis.length > 0 ? "04" : "03"}</span><div><small>Impression</small><h3>诊断印象</h3></div></header>
                    <p>{report.impression ?? "后端未提供诊断印象。"}</p>
                    {report.targetedCandidate ? <div className="report-targeted-review"><small>靶向复核线索</small><strong>{[report.targetedCandidate.family, report.targetedCandidate.focus].filter(Boolean).join(" / ") || "待复核"}</strong><p>{report.targetedCandidate.reason ?? "未提供复核原因。"}</p></div> : null}
                  </section>

                  {report.recommendations.length > 0 ? (
                    <section className="clinical-report-section"><header><span>05</span><div><small>Recommendations</small><h3>进一步检查与处置建议</h3></div></header><TextList items={report.recommendations} /></section>
                  ) : null}

                  {(report.limitations.length > 0 || report.familiesNotAssessed.length > 0 || report.reviewReason) ? (
                    <section className="clinical-report-section clinical-report-section--limitations">
                      <header><span>!</span><div><small>Limitations & Review</small><h3>局限性与复核事项</h3></div></header>
                      {report.reviewReason ? <p className="report-review-reason">{report.reviewReason}</p> : null}
                      <TextList items={report.limitations} empty="未声明其他局限。" />
                      {report.familiesNotAssessed.length > 0 ? <div className="report-unassessed"><small>未评估系统</small><p>{report.familiesNotAssessed.join("、")}</p></div> : null}
                    </section>
                  ) : null}

                  <footer className="clinical-report-footer">
                    <div><Icon name="shield" /><p>本报告为 AI 辅助影像分析结果，必须由执业兽医结合病史、体格检查及其他检验结果复核。</p></div>
                    <dl><div><dt>内容校验</dt><dd title={current.content_sha256}>{current.content_sha256.slice(0, 16)}…</dd></div><div><dt>证据影像</dt><dd>{report.sourceRefs.length} 条引用</dd></div></dl>
                    <button className="raw-report-toggle" onClick={() => setShowRaw((value) => !value)}>{showRaw ? "收起原始数据" : "查看原始数据与审计字段"}<Icon name="chevron" /></button>
                    {showRaw ? <pre className="raw-json">{JSON.stringify(current.content_json, null, 2)}</pre> : null}
                  </footer>
                </>
              )}
            </article>
          </div>
        </>
      )}
    </section>
  );
}
