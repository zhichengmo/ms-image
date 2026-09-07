import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  AnatomyLocalizationResponse,
  LegendResponse,
  PrepareViewResponse,
  TaskResponse,
} from "../types/runtime";
import { LocalizationViewer } from "./LocalizationPanel";
import { Button, ErrorNotice, Icon, LoadingState, StatusBadge } from "./ui";

interface ReportImagingPanelProps {
  localizationTask: TaskResponse | null;
  result: AnatomyLocalizationResponse | null;
  view: PrepareViewResponse | null;
  legend: LegendResponse | null;
  loading: boolean;
  error: string | null;
  focusImageId: string | null;
  onLoad: () => void;
  onRefreshView: (imageIds?: string[] | null) => void;
}

export function ReportImagingPanel({
  localizationTask,
  result,
  view,
  legend,
  loading,
  error,
  focusImageId,
  onLoad,
  onRefreshView,
}: ReportImagingPanelProps) {
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

  useEffect(() => {
    if (focusImageId && view?.images.some((image) => image.image_id === focusImageId)) {
      setSelectedImageId(focusImageId);
    }
  }, [focusImageId, view?.images]);

  const selectedView =
    view?.images.find((image) => image.image_id === selectedImageId) ?? view?.images[0] ?? null;
  const selectedResult =
    result?.result.images.find((image) => image.image_id === selectedView?.image_id) ?? null;

  const systemMap = useMemo(
    () => new Map(legend?.systems.map((system) => [system.system, system]) ?? []),
    [legend],
  );
  const labelMap = useMemo(
    () => new Map(
      legend?.systems.flatMap((system) =>
        system.labels.map((label) => [label.label, label.display_name] as const),
      ) ?? [],
    ),
    [legend],
  );

  const groupedOrgans = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const organ of selectedResult?.organs ?? []) {
      const labels = groups.get(organ.system) ?? [];
      labels.push(labelMap.get(organ.label) ?? organ.label);
      groups.set(organ.system, labels);
    }
    return [...groups.entries()];
  }, [labelMap, selectedResult?.organs]);

  const refreshSelected = useCallback(() => {
    onRefreshView(selectedView ? [selectedView.image_id] : null);
  }, [onRefreshView, selectedView]);

  const ready = Boolean(result && view && legend);
  const isDatasetAnnotation = legend?.systems.some((system) => system.system === "dataset_annotation") ?? false;
  const localizationLabel = isDatasetAnnotation ? "数据集标注" : "解剖定位";
  const evidenceFocusActive = Boolean(focusImageId && selectedView?.image_id === focusImageId);

  return (
    <section className={`report-imaging${evidenceFocusActive ? " report-imaging--evidence-focused" : ""}`} aria-labelledby="report-imaging-heading">
      <header className="report-imaging__head">
        <div>
          <span className="eyebrow">影像与定位证据</span>
          <h2 id="report-imaging-heading">X-Ray 阅片区</h2>
        </div>
        <div className="report-imaging__status">
          {localizationTask ? <StatusBadge status={localizationTask.execution_status} /> : null}
          <Button tone="ghost" disabled={loading || !localizationTask} onClick={onLoad}>
            <Icon name="refresh" />刷新
          </Button>
        </div>
      </header>

      <p className="report-imaging__note">
        当前展示为原始 X 光影像上的{localizationLabel}框（bbox），不是像素级分割 mask。定位链与诊断报告主链独立执行。
      </p>

      {evidenceFocusActive ? (
        <div className="report-imaging__focus" aria-live="polite">
          <Icon name="eye" />
          <span><strong>报告证据已定位</strong>当前影像由右侧“证据影像”链接选中，框选仅表示{localizationLabel}区域，不代表病灶范围。</span>
        </div>
      ) : null}

      {error && !ready ? (
        <ErrorNotice message={error} onRetry={onLoad} />
      ) : loading && !ready ? (
        <LoadingState label="正在读取原始影像和定位数据" />
      ) : !localizationTask ? (
        <div className="report-imaging__empty">
          <Icon name="image" />
          <strong>尚未创建定位任务</strong>
          <p>创建诊断任务后，展示链会独立启动并生成可视化定位数据。</p>
        </div>
      ) : localizationTask.execution_status !== "completed" && !ready ? (
        <div className="report-imaging__empty report-imaging__empty--running">
          <span className="spinner" aria-hidden="true" />
          <strong>定位展示链正在处理</strong>
          <p>影像展示会在定位链完成后出现；诊断主链正在并行执行，不需要等待本步骤。</p>
        </div>
      ) : !ready ? (
        <div className="report-imaging__empty">
          <Icon name="image" />
          <strong>影像证据暂不可用</strong>
          <p>定位任务已结束，但结果或短效影像链接尚未返回。</p>
          <Button onClick={onLoad}>重新读取</Button>
        </div>
      ) : (
        <>
          <div className="report-image-tabs" aria-label="X-Ray 影像序列">
            {view!.images.map((image) => {
              const imageResult = result!.result.images.find((item) => item.image_id === image.image_id);
              return (
                <button
                  aria-pressed={image.image_id === selectedView?.image_id}
                  className={image.image_id === selectedView?.image_id ? "report-image-tab report-image-tab--active" : "report-image-tab"}
                  key={image.image_id}
                  type="button"
                  onClick={() => setSelectedImageId(image.image_id)}
                >
                  <span>#{image.sequence_no}</span>
                  <div>
                    <strong>{image.projection}</strong>
                    <small>{imageResult?.organs.length ?? 0} 个定位框</small>
                  </div>
                </button>
              );
            })}
          </div>

          {selectedView ? (
            <LocalizationViewer
              key={selectedView.image_id}
              viewImage={selectedView}
              resultImage={selectedResult}
              legend={legend!}
              onExpired={refreshSelected}
            />
          ) : null}

          <div className="report-segmentation-data">
            <div className="report-segmentation-data__head">
              <div>
                <span className="eyebrow">定位数据</span>
                <h3>{selectedResult?.organs.length ?? 0} 个{isDatasetAnnotation ? "标注区域" : "解剖区域"}</h3>
              </div>
              <span>{result!.result.contract_version}</span>
            </div>
            {groupedOrgans.length > 0 ? (
              <div className="report-organ-groups">
                {groupedOrgans.map(([system, labels]) => {
                  const legendSystem = systemMap.get(system);
                  return (
                    <section key={system}>
                      <header>
                        <span style={{ backgroundColor: legendSystem?.color ?? "#39C982" }} />
                        <strong>{legendSystem?.display_name ?? system}</strong>
                        <small>{labels.length}</small>
                      </header>
                      <p>{labels.join("、")}</p>
                    </section>
                  );
                })}
              </div>
            ) : (
              <p className="report-segmentation-data__empty">
                {selectedResult?.reason_code ?? "本张影像未返回可展示的定位结果。"}
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
