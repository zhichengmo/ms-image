import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { LocalizationPanel } from "../components/LocalizationPanel";
import { ReportPanel } from "../components/ReportPanel";
import { TaskBoard } from "../components/TaskBoard";
import { type UploadSlot, UploadPanel } from "../components/UploadPanel";
import { Button, ErrorNotice, Icon } from "../components/ui";
import { useTaskPolling } from "../hooks/useTaskPolling";
import { ApiError, describeApiError, RuntimeApi } from "../lib/api";
import { inspectFile } from "../lib/fileMetadata";
import {
  type PersistedImageState,
  type WorkflowState,
  loadWorkflow,
  persistWorkflow,
  resetWorkflow,
} from "../state/workflow";
import type {
  AnatomyLocalizationResponse,
  AnatomyLocalizationTaskSummary,
  ImageResponse,
  LegendResponse,
  PrepareViewResponse,
  QualityReviewResponse,
  ReportResponse,
  TaskResponse,
} from "../types/runtime";

type TaskKey = "quality" | "diagnose" | "localization";

export function XrayWorkspacePage() {
  const mainRef = useRef<HTMLElement>(null);
  const [workflow, setWorkflow] = useState<WorkflowState>(() => loadWorkflow());
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [connected, setConnected] = useState(false);
  const [connectionOpen, setConnectionOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollingErrors, setPollingErrors] = useState<Partial<Record<TaskKey, string>>>({});
  const [pollingRetryKey, setPollingRetryKey] = useState(0);
  const [qualityResult, setQualityResult] = useState<QualityReviewResponse | null>(null);
  const [currentReport, setCurrentReport] = useState<ReportResponse | null>(null);
  const [reportHistory, setReportHistory] = useState<ReportResponse[]>([]);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [currentLocalization, setCurrentLocalization] = useState<AnatomyLocalizationTaskSummary | null>(null);
  const [localizationHistory, setLocalizationHistory] = useState<AnatomyLocalizationTaskSummary[]>([]);
  const [localizationResult, setLocalizationResult] = useState<AnatomyLocalizationResponse | null>(null);
  const [localizationView, setLocalizationView] = useState<PrepareViewResponse | null>(null);
  const [legend, setLegend] = useState<LegendResponse | null>(null);
  const [localizationLoading, setLocalizationLoading] = useState(false);
  const [localizationError, setLocalizationError] = useState<string | null>(null);

  const api = useMemo(() => {
    try {
      if (!connected || !username.trim() || !password) return null;
      return new RuntimeApi(workflow.baseUrl, username, password);
    } catch {
      return null;
    }
  }, [connected, password, username, workflow.baseUrl]);
  const pollingError = Object.values(pollingErrors)[0] ?? null;

  useEffect(() => persistWorkflow(workflow), [workflow]);

  const updateWorkflow = useCallback((patch: Partial<WorkflowState>) => {
    setWorkflow((current) => ({ ...current, ...patch }));
  }, []);

  const onTask = useCallback((key: TaskKey, task: TaskResponse) => {
    setWorkflow((current) => ({
      ...current,
      qualityTask: key === "quality" ? task : current.qualityTask,
      diagnoseTask: key === "diagnose" ? task : current.diagnoseTask,
      localizationTask: key === "localization" ? task : current.localizationTask,
      reportId: key === "diagnose" ? task.current_report_id : current.reportId,
    }));
  }, []);

  const completedQualityTaskId = workflow.qualityTask?.execution_status === "completed"
    ? workflow.qualityTask.id
    : null;

  useEffect(() => {
    let active = true;
    if (api && completedQualityTaskId) {
      void api.getQualityReview(completedQualityTaskId)
        .then((result) => { if (active) setQualityResult(result); })
        .catch((reason) => { if (active) setError(describeApiError(reason)); });
    }
    return () => { active = false; };
  }, [api, completedQualityTaskId]);

  useTaskPolling({
    api,
    targets: [
      { key: "quality", task: workflow.qualityTask },
      { key: "diagnose", task: workflow.diagnoseTask },
      { key: "localization", task: workflow.localizationTask },
    ],
    retryKey: pollingRetryKey,
    onTask,
    onError: (key, message) => setPollingErrors((current) => ({
      ...current,
      [key]: describeApiError(new Error(message)),
    })),
    onRecovered: (key) => setPollingErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    }),
  });

  const connect = async () => {
    setError(null);
    setBusy(true);
    try {
      const candidate = new RuntimeApi(workflow.baseUrl, username, password);
      await candidate.readiness();
      await candidate.verifyAuthentication();
      setConnected(true);
      setPollingErrors({});
      setConnectionOpen(false);
      window.requestAnimationFrame(() => {
        mainRef.current?.focus({ preventScroll: true });
        window.scrollTo({ top: 0, behavior: "instant" });
      });
    } catch (reason) {
      setConnected(false);
      setError(describeApiError(reason));
    } finally {
      setBusy(false);
    }
  };

  const uploadWorkflow = async (slots: UploadSlot[]) => {
    if (!api) {
      setConnectionOpen(true);
      setError("请先使用 Basic Auth 连接 Runtime API。凭证只保存在当前页面内存中。");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const sessionStartedAt = workflow.sessionStartedAt ?? new Date().toISOString();
      if (!workflow.sessionStartedAt) {
        updateWorkflow({ sessionStartedAt });
      }

      let sessionId = workflow.sessionId;
      if (!sessionId) {
        const session = await api.createSession({
          sourceSystem: "ms-image-frontend",
          sourceSessionId: workflow.runId,
          sourceMedicalRecordId: workflow.caseKey,
          subjectId: workflow.subjectId,
          requestId: `session-${workflow.runId}`,
          startedAt: sessionStartedAt,
        });
        sessionId = session.id;
        setWorkflow((current) => ({
          ...current,
          sessionId: session.id,
          sessionStateVersion: session.state_version,
        }));
      }

      let study = workflow.studyId
        ? (await api.getStudy(workflow.studyId)).study
        : await api.createStudy({
            sessionId,
            sourceStudyId: `${workflow.caseKey}-${workflow.runId}`,
            imageCount: slots.length,
          });
      let studyDetail = await api.getStudy(study.id);
      study = studyDetail.study;

      let seriesId = workflow.seriesId ?? studyDetail.series[0]?.id ?? null;
      if (!seriesId) {
        const series = await api.createSeries({
          studyId: study.id,
          seriesKey: `series-${workflow.runId}`,
          imageCount: slots.length,
        });
        seriesId = series.id;
        studyDetail = await api.getStudy(study.id);
        study = studyDetail.study;
      }
      setWorkflow((current) => ({
        ...current,
        studyId: study.id,
        studyRevisionId: study.revision_id,
        studyStateVersion: study.state_version,
        studyStatus: study.status,
        seriesId,
      }));

      const remoteImages = await api.listImages(seriesId);
      const remoteBySequence = new Map(
        remoteImages.map((image) => [image.sequence_no, image]),
      );
      if (remoteImages.length > 0) {
        setWorkflow((current) => ({
          ...current,
          images: slots.map((slot) => {
            const persisted = current.images.find(
              (image) => image.sequenceNo === slot.sequenceNo,
            );
            const remote = remoteBySequence.get(slot.sequenceNo);
            if (!remote) {
              return persisted ?? {
                sequenceNo: slot.sequenceNo,
                name: slot.file?.name ?? `影像 ${slot.sequenceNo}`,
                projection: slot.projection,
                imageId: null,
                stateVersion: null,
                status: "pending",
                errorCode: null,
              };
            }
            return {
              sequenceNo: slot.sequenceNo,
              name: persisted?.name ?? slot.file?.name ?? `影像 ${slot.sequenceNo}`,
              projection: remote.projection ?? persisted?.projection ?? slot.projection,
              imageId: remote.id,
              stateVersion: remote.state_version,
              status: remote.status,
              errorCode: remote.error_code,
            };
          }),
        }));
      }

      const syncImage = (sequenceNo: number, image: ImageResponse) => {
        setWorkflow((current) => {
          const existing = current.images.find((item) => item.sequenceNo === sequenceNo);
          const next: PersistedImageState = {
            sequenceNo,
            name: existing?.name ?? `影像 ${sequenceNo}`,
            projection: image.projection ?? existing?.projection ?? "",
            imageId: image.id,
            stateVersion: image.state_version,
            status: image.status,
            errorCode: image.error_code,
          };
          return {
            ...current,
            images: [
              ...current.images.filter((item) => item.sequenceNo !== sequenceNo),
              next,
            ].sort((a, b) => a.sequenceNo - b.sequenceNo),
          };
        });
      };

      const waitUntilReady = async (sequenceNo: number, initial: ImageResponse) => {
        let image = initial;
        let attempts = 0;
        while (image.status !== "ready") {
          if (["quarantined", "deleted", "superseded"].includes(image.status)) {
            throw new ApiError(`第 ${sequenceNo} 张影像校验失败`, 409, image.error_code);
          }
          if (image.status === "uploading") {
            throw new Error(`第 ${sequenceNo} 张影像尚未完成上传，请重新选择原文件。`);
          }
          if (++attempts > 60) throw new Error(`第 ${sequenceNo} 张影像校验超时`);
          syncImage(sequenceNo, image);
          await new Promise((resolve) => window.setTimeout(
            resolve,
            image.next_validation_at
              ? Math.max(1_000, Math.min(5_000, Date.parse(image.next_validation_at) - Date.now()))
              : 1_500,
          ));
          image = await api.getImage(image.id);
        }
        syncImage(sequenceNo, image);
        remoteBySequence.set(sequenceNo, image);
      };

      for (const slot of slots) {
        const remote = remoteBySequence.get(slot.sequenceNo);
        if (remote?.status === "ready") {
          syncImage(slot.sequenceNo, remote);
          continue;
        }
        if (remote?.status === "validating") {
          await waitUntilReady(slot.sequenceNo, remote);
          continue;
        }
        if (!slot.file) throw new Error(`第 ${slot.sequenceNo} 张影像文件已丢失，请重新选择。`);
        setWorkflow((current) => ({
          ...current,
          images: [
            ...current.images.filter((image) => image.sequenceNo !== slot.sequenceNo),
            {
              sequenceNo: slot.sequenceNo,
              name: slot.file!.name,
              projection: slot.projection,
              imageId: null,
              stateVersion: null,
              status: "hashing",
              errorCode: null,
            },
          ].sort((a, b) => a.sequenceNo - b.sequenceNo),
        }));
        const metadata = await inspectFile(slot.file);
        const ticket = await api.prepareUpload({
          seriesId,
          logicalImageKey: `image-${slot.sequenceNo}-${workflow.runId}`,
          sequenceNo: slot.sequenceNo,
          fileFormat: metadata.fileFormat,
          sha256: metadata.sha256,
          sizeBytes: metadata.sizeBytes,
          contentType: metadata.contentType,
          projection: slot.projection,
        });
        await api.uploadObject(
          ticket.signed_url,
          slot.file,
          metadata.contentType,
          ticket.required_headers,
        );
        const image = await api.completeUpload({
          imageId: ticket.image.id,
          stateVersion: ticket.image.state_version,
          generation: ticket.generation,
          traceId: `image-complete-${slot.sequenceNo}-${workflow.runId}`,
        });
        await waitUntilReady(slot.sequenceNo, image);
      }

      const detail = await api.getStudy(study.id);
      const finalized = await api.finalizeStudy({
        studyId: study.id,
        stateVersion: detail.study.state_version,
        revisionId: detail.study.revision_id,
      });
      setWorkflow((current) => ({
        ...current,
        studyRevisionId: finalized.revision_id,
        studyStateVersion: finalized.state_version,
        studyStatus: finalized.status,
      }));
    } catch (reason) {
      setError(describeApiError(reason));
    } finally {
      setBusy(false);
    }
  };

  const requireStudy = () => {
    if (!api || !workflow.studyId || !workflow.studyRevisionId || workflow.studyStatus !== "ready") {
      throw new Error("检查尚未冻结或 Runtime 未连接。");
    }
    return { api, studyId: workflow.studyId, revisionId: workflow.studyRevisionId };
  };

  const createQuality = async () => {
    setBusy(true); setError(null);
    try {
      const context = requireStudy();
      const task = await context.api.createQualityReview({
        studyId: context.studyId,
        revisionId: context.revisionId,
        requestId: `quality-${workflow.runId}`,
        species: workflow.species,
        traceId: `quality-trace-${workflow.runId}`,
      });
      updateWorkflow({ qualityTask: task });
    } catch (reason) { setError(describeApiError(reason)); } finally { setBusy(false); }
  };

  const createDiagnose = async () => {
    setBusy(true); setError(null);
    try {
      const context = requireStudy();
      if (!workflow.qualityTask || workflow.qualityTask.execution_status !== "completed") {
        throw new Error("Quality Review 尚未完成。");
      }
      const diagnoseTask = await context.api.createDiagnoseTask({
        studyId: context.studyId,
        revisionId: context.revisionId,
        requestId: `diagnose-${workflow.runId}`,
        species: workflow.species,
        qualityTaskId: workflow.qualityTask.id,
        chiefComplaint: workflow.chiefComplaint,
        studyReason: workflow.studyReason,
        recordedAt: new Date().toISOString(),
        traceId: `diagnose-trace-${workflow.runId}`,
      });
      updateWorkflow({
        diagnoseTask,
        reportId: diagnoseTask.current_report_id,
      });

      try {
        const localizationTask = await context.api.createLocalizationTask({
          studyId: context.studyId,
          revisionId: context.revisionId,
          requestId: `localization-${workflow.runId}`,
          species: workflow.species,
          diagnoseTaskId: diagnoseTask.id,
          traceId: `localization-trace-${workflow.runId}`,
        });
        updateWorkflow({ localizationTask });
      } catch (localizationReason) {
        setError(`诊断主链已启动，但展示链启动失败：${describeApiError(localizationReason)}`);
      }
    } catch (reason) { setError(describeApiError(reason)); } finally { setBusy(false); }
  };

  const createLocalization = async () => {
    setBusy(true); setError(null);
    try {
      const context = requireStudy();
      if (!workflow.diagnoseTask) {
        throw new Error("Diagnose Task 尚未创建。");
      }
      const task = await context.api.createLocalizationTask({
        studyId: context.studyId,
        revisionId: context.revisionId,
        requestId: `localization-${workflow.runId}`,
        species: workflow.species,
        diagnoseTaskId: workflow.diagnoseTask.id,
        traceId: `localization-trace-${workflow.runId}`,
      });
      updateWorkflow({ localizationTask: task });
    } catch (reason) { setError(describeApiError(reason)); } finally { setBusy(false); }
  };

  const cancelTask = async (key: TaskKey, task: TaskResponse) => {
    if (!api) return;
    setBusy(true); setError(null);
    try {
      let latest = task;
      try {
        latest = await api.getTask(task.id);
      } catch { /* cancel with the latest locally known state */ }
      const cancelled = await api.cancelTask(latest.id, latest.state_version);
      onTask(key, cancelled);
    } catch (reason) { setError(describeApiError(reason)); } finally { setBusy(false); }
  };

  const loadReports = useCallback(async () => {
    if (!api || !workflow.diagnoseTask) return;
    setReportLoading(true); setReportError(null);
    try {
      const [current, history] = await Promise.all([
        api.getCurrentReport(workflow.diagnoseTask.id),
        api.getReportHistory(workflow.diagnoseTask.id),
      ]);
      setCurrentReport(current);
      setReportHistory(history);
      if (current) updateWorkflow({ reportId: current.id });
    } catch (reason) { setReportError(describeApiError(reason)); } finally { setReportLoading(false); }
  }, [api, updateWorkflow, workflow.diagnoseTask]);

  const selectReport = async (reportId: string) => {
    if (!api) return;
    setReportLoading(true); setReportError(null);
    try { setCurrentReport(await api.getReport(reportId)); }
    catch (reason) { setReportError(describeApiError(reason)); }
    finally { setReportLoading(false); }
  };

  const loadLocalization = useCallback(async (taskId?: string) => {
    if (!api || !workflow.diagnoseTask) return;
    setLocalizationLoading(true); setLocalizationError(null);
    try {
      const [current, historyResult, legendResult] = await Promise.all([
        api.getCurrentLocalization(workflow.diagnoseTask.id),
        api.getLocalizationHistory(workflow.diagnoseTask.id),
        api.getLocalizationLegend(),
      ]);
      setCurrentLocalization(current);
      setLocalizationHistory(historyResult.items);
      setLegend(legendResult);
      const resolvedTaskId = taskId ?? workflow.localizationTask?.id ?? current?.task_id;
      if (resolvedTaskId) {
        const [resultData, viewData] = await Promise.all([
          api.getLocalizationResult(resolvedTaskId),
          api.prepareLocalizationView(resolvedTaskId),
        ]);
        setLocalizationResult(resultData);
        setLocalizationView(viewData);
      }
    } catch (reason) { setLocalizationError(describeApiError(reason)); }
    finally { setLocalizationLoading(false); }
  }, [api, workflow.diagnoseTask, workflow.localizationTask?.id]);

  const refreshView = useCallback(async (imageIds: string[] | null = null) => {
    if (!api || !localizationResult) return;
    setLocalizationLoading(true); setLocalizationError(null);
    try {
      const refreshed = await api.prepareLocalizationView(localizationResult.task_id, imageIds);
      if (imageIds && localizationView) {
        const replacements = new Map(refreshed.images.map((image) => [image.image_id, image]));
        setLocalizationView({ ...localizationView, expires_in: refreshed.expires_in, images: localizationView.images.map((image) => replacements.get(image.image_id) ?? image) });
      } else setLocalizationView(refreshed);
    } catch (reason) { setLocalizationError(describeApiError(reason)); }
    finally { setLocalizationLoading(false); }
  }, [api, localizationResult, localizationView]);

  const clearCase = () => {
    if (!window.confirm("清除当前页面保存的资源 ID 和状态？服务端数据不会被删除。")) return;
    setWorkflow(resetWorkflow(workflow.baseUrl));
    setQualityResult(null); setCurrentReport(null); setReportHistory([]);
    setCurrentLocalization(null); setLocalizationHistory([]); setLocalizationResult(null); setLocalizationView(null);
    setError(null); setPollingErrors({}); setPollingRetryKey(0);
  };

  const navItems = [
    { id: "workflow" as const, label: "检查流程", icon: "activity" as const },
    { id: "report" as const, label: "诊断报告", icon: "report" as const },
    { id: "localization" as const, label: "器官定位", icon: "image" as const },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand__mark"><Icon name="activity" /></span><div><strong>MS-IMAGE</strong><small>X-RAY WORKSPACE</small></div></div>
        <nav aria-label="工作台导航">
          {navItems.map((item) => (
            <button className={workflow.activeView === item.id ? "nav-item nav-item--active" : "nav-item"} key={item.id} onClick={() => updateWorkflow({ activeView: item.id })}>
              <Icon name={item.icon} /><span>{item.label}</span>
              {item.id === "report" && workflow.diagnoseTask?.execution_status === "completed" ? <i /> : null}
              {item.id === "localization" && workflow.localizationTask?.execution_status === "completed" ? <i /> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar__footer">
          <div className="connection-state"><span className={connected ? "connection-state__dot connection-state__dot--online" : "connection-state__dot"} /><div><strong>{connected ? "Runtime 已连接" : "Runtime 未连接"}</strong><small>{workflow.baseUrl.replace(/^https?:\/\//, "")}</small></div></div>
          <Button tone="ghost" onClick={() => setConnectionOpen(true)}>连接设置</Button>
        </div>
      </aside>

      <div className="app-content">
        <header className="topbar">
          <div><span className="topbar__context">影像辅助诊断</span>{workflow.caseKey ? <><span className="topbar__divider" /><strong>{workflow.caseKey}</strong></> : null}</div>
          <div className="topbar__actions"><span className="privacy-note"><Icon name="shield" />Basic 凭证与短效链接不持久化</span><Button tone="ghost" onClick={clearCase}>新建检查</Button></div>
        </header>

        <main id="main-content" ref={mainRef} tabIndex={-1}>
          {error ? <ErrorNotice message={error} onRetry={() => setError(null)} /> : null}
          {pollingError ? (
            <ErrorNotice
              message={pollingError}
              onRetry={() => {
                setPollingErrors({});
                setPollingRetryKey((current) => current + 1);
              }}
            />
          ) : null}
          {workflow.activeView === "workflow" ? (
            <div className="workflow-page">
              <div className="page-intro"><div><span className="eyebrow">临床影像工作台</span><h1>从原始影像到辅助报告</h1><p>完成影像校验和质量审查后，并行执行诊断主链与器官定位展示链。</p></div><div className="page-intro__meta"><span>{workflow.species === "cat" ? "猫" : "犬"}</span><span>{workflow.images.length || 2} 张影像</span></div></div>
              <UploadPanel workflow={workflow} busy={busy} onDetailsChange={updateWorkflow} onUpload={uploadWorkflow} />
              <TaskBoard
                studyReady={Boolean(workflow.studyId && workflow.studyStatus === "ready" && workflow.images.length >= 2 && workflow.images.every((image) => image.status === "ready"))}
                qualityTask={workflow.qualityTask}
                diagnoseTask={workflow.diagnoseTask}
                localizationTask={workflow.localizationTask}
                qualityResult={qualityResult}
                busy={busy}
                onCreateQuality={createQuality}
                onCreateDiagnose={createDiagnose}
                onCreateLocalization={createLocalization}
                onCancel={cancelTask}
              />
            </div>
          ) : null}
          {workflow.activeView === "report" ? (
            <ReportPanel
              diagnoseTask={workflow.diagnoseTask}
              localizationTask={workflow.localizationTask}
              current={currentReport}
              history={reportHistory}
              loading={reportLoading}
              error={reportError}
              localizationResult={localizationResult}
              localizationView={localizationView}
              legend={legend}
              localizationLoading={localizationLoading}
              localizationError={localizationError}
              onLoad={loadReports}
              onSelect={selectReport}
              onLoadLocalization={() => loadLocalization()}
              onRefreshLocalizationView={refreshView}
            />
          ) : null}
          {workflow.activeView === "localization" ? (
            <LocalizationPanel
              diagnoseTask={workflow.diagnoseTask}
              localizationTask={workflow.localizationTask}
              current={currentLocalization}
              history={localizationHistory}
              result={localizationResult}
              view={localizationView}
              legend={legend}
              loading={localizationLoading}
              error={localizationError}
              onLoad={() => loadLocalization()}
              onRefreshView={refreshView}
              onSelectHistory={loadLocalization}
            />
          ) : null}
        </main>
      </div>

      {connectionOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section aria-labelledby="connection-heading" aria-modal="true" className="modal" role="dialog">
            <div className="modal__head"><div><span className="eyebrow">Runtime 连接</span><h2 id="connection-heading">连接影像服务</h2></div>{connected ? <Button tone="ghost" aria-label="关闭" onClick={() => setConnectionOpen(false)}><Icon name="close" /></Button> : null}</div>
            <p>Basic Auth 凭证仅保存在当前标签页内存中，刷新页面后需要重新输入。</p>
            <form onSubmit={(event) => { event.preventDefault(); void connect(); }}>
              <label className="field"><span>Runtime API Base URL</span><input disabled={busy} value={workflow.baseUrl} onChange={(event) => updateWorkflow({ baseUrl: event.target.value })} /></label>
              <label className="field"><span>用户名</span><input autoComplete="username" disabled={busy} placeholder="Basic Auth 用户名" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
              <label className="field"><span>密码</span><input autoComplete="current-password" disabled={busy} placeholder="Basic Auth 密码" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
              <div className="modal__note"><Icon name="shield" /><span>页面不会把用户名、密码、signed URL 或完整医疗报告写入 localStorage。</span></div>
              <div className="modal__actions"><Button tone="primary" disabled={busy || !username.trim() || !password} type="submit">{busy ? "正在检查服务" : "使用 Basic Auth 连接"}<Icon name="arrow" /></Button></div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
