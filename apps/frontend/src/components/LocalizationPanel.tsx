import {
  type PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type {
  AnatomyLocalizationResponse,
  AnatomyLocalizationTaskSummary,
  LegendResponse,
  LocalizationImageResult,
  PrepareViewResponse,
  TaskResponse,
  ViewImage,
} from "../types/runtime";
import {
  Button,
  EmptyState,
  ErrorNotice,
  formatDateTime,
  Icon,
  LoadingState,
  StatusBadge,
} from "./ui";

interface LocalizationPanelProps {
  diagnoseTask: TaskResponse | null;
  localizationTask: TaskResponse | null;
  current: AnatomyLocalizationTaskSummary | null;
  history: AnatomyLocalizationTaskSummary[];
  result: AnatomyLocalizationResponse | null;
  view: PrepareViewResponse | null;
  legend: LegendResponse | null;
  loading: boolean;
  error: string | null;
  onLoad: () => void;
  onRefreshView: (imageIds?: string[] | null) => void;
  onSelectHistory: (taskId: string) => void;
}

function secondsUntil(value: string): number {
  return Math.max(0, Math.floor((Date.parse(value) - Date.now()) / 1000));
}

function formatExpiry(value: string): string {
  const seconds = secondsUntil(value);
  if (seconds <= 0) return "已过期";
  if (seconds < 60) return `${seconds} 秒后过期`;
  return `${Math.ceil(seconds / 60)} 分钟后过期`;
}

export function LocalizationViewer({
  viewImage,
  resultImage,
  legend,
  onExpired,
}: {
  viewImage: ViewImage;
  resultImage: LocalizationImageResult | null;
  legend: LegendResponse;
  onExpired: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [natural, setNatural] = useState({ width: 0, height: 0 });
  const [container, setContainer] = useState({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [drag, setDrag] = useState<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const [activeSystems, setActiveSystems] = useState<Set<string>>(
    () => new Set(legend.systems.map((system) => system.system)),
  );
  const [imageError, setImageError] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      setContainer({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const handler = () => setFullscreen(document.fullscreenElement === containerRef.current);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const metrics = useMemo(() => {
    if (!natural.width || !natural.height || !container.width || !container.height) return null;
    const scale = Math.min(container.width / natural.width, container.height / natural.height);
    const width = natural.width * scale;
    const height = natural.height * scale;
    return {
      width,
      height,
      left: (container.width - width) / 2,
      top: (container.height - height) / 2,
    };
  }, [container, natural]);

  const systemMap = useMemo(
    () => new Map(legend.systems.map((system) => [system.system, system])),
    [legend],
  );

  const labelMap = useMemo(() => {
    const entries = legend.systems.flatMap((system) =>
      system.labels.map((label) => [label.label, label.display_name] as const),
    );
    return new Map(entries);
  }, [legend]);

  const reset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (zoom <= 1) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y });
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    setPan({ x: drag.panX + event.clientX - drag.x, y: drag.panY + event.clientY - drag.y });
  };

  const toggleSystem = (system: string) => {
    setActiveSystems((current) => {
      const next = new Set(current);
      if (next.has(system)) next.delete(system);
      else next.add(system);
      return next;
    });
  };

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;
    if (document.fullscreenElement) await document.exitFullscreen();
    else await containerRef.current.requestFullscreen();
  };

  const expired = secondsUntil(viewImage.expires_at) <= 0;
  const visibleOrgans = resultImage?.organs.filter((organ) => activeSystems.has(organ.system)) ?? [];

  return (
    <div className={`viewer-shell ${fullscreen ? "viewer-shell--fullscreen" : ""}`}>
      <div className="viewer-toolbar" aria-label="影像查看工具">
        <div>
          <strong>影像 #{viewImage.sequence_no}</strong>
          <span>{viewImage.projection}</span>
        </div>
        <div className="viewer-toolbar__actions">
          <Button tone="ghost" aria-label="缩小" disabled={zoom <= 1} onClick={() => setZoom((value) => Math.max(1, value - 0.25))}><Icon name="minus" /></Button>
          <span className="zoom-value">{Math.round(zoom * 100)}%</span>
          <Button tone="ghost" aria-label="放大" disabled={zoom >= 4} onClick={() => setZoom((value) => Math.min(4, value + 0.25))}><Icon name="plus" /></Button>
          <Button tone="ghost" onClick={reset}><Icon name="refresh" />复位</Button>
          <Button tone="ghost" onClick={toggleFullscreen}><Icon name="expand" />{fullscreen ? "退出全屏" : "全屏"}</Button>
        </div>
      </div>

      <div
        className={`viewer ${zoom > 1 ? "viewer--zoomed" : ""}`}
        ref={containerRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={() => setDrag(null)}
        onPointerCancel={() => setDrag(null)}
      >
        {expired || imageError ? (
          <div className="viewer-expired" role="alert">
            <Icon name="image" />
            <strong>{expired ? "影像链接已过期" : "影像加载失败"}</strong>
            <p>短时效链接不会保存。请重新向服务端申请。</p>
            <Button tone="primary" onClick={onExpired}><Icon name="refresh" />重新申请</Button>
          </div>
        ) : (
          <div
            className="viewer-transform"
            style={{ transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})` }}
          >
            <img
              alt={`X-Ray 影像 ${viewImage.sequence_no}，投照位 ${viewImage.projection}`}
              draggable={false}
              ref={imageRef}
              src={viewImage.signed_url}
              onError={() => setImageError(true)}
              onLoad={(event) => setNatural({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })}
            />
            {metrics ? (
              <div className="overlay" aria-label="器官定位框">
                {visibleOrgans.map((organ, index) => {
                  const [xMin, yMin, xMax, yMax] = organ.bbox;
                  const system = systemMap.get(organ.system);
                  const color = system?.color ?? "#22D3EE";
                  return (
                    <div
                      className="bbox"
                      key={`${organ.label}-${index}`}
                      style={{
                        borderColor: color,
                        color,
                        left: metrics.left + xMin * metrics.width,
                        top: metrics.top + yMin * metrics.height,
                        width: (xMax - xMin) * metrics.width,
                        height: (yMax - yMin) * metrics.height,
                      }}
                    >
                      <span style={{ backgroundColor: color }}>{labelMap.get(organ.label) ?? organ.label}</span>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        )}
      </div>

      <div className="viewer-footer">
        <span className={expired ? "expiry expiry--expired" : "expiry"}>{formatExpiry(viewImage.expires_at)}</span>
        <div className="legend-list" aria-label="器官系统图例">
          {legend.systems
            .slice()
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((system) => (
              <label className={activeSystems.has(system.system) ? "legend-chip legend-chip--active" : "legend-chip"} key={system.system}>
                <input type="checkbox" checked={activeSystems.has(system.system)} onChange={() => toggleSystem(system.system)} />
                <span style={{ backgroundColor: system.color }} />
                {system.display_name}
              </label>
            ))}
        </div>
      </div>
    </div>
  );
}

export function LocalizationPanel({
  diagnoseTask,
  localizationTask,
  current,
  history,
  result,
  view,
  legend,
  loading,
  error,
  onLoad,
  onRefreshView,
  onSelectHistory,
}: LocalizationPanelProps) {
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const selectedView =
    view?.images.find((image) => image.image_id === selectedImageId) ?? view?.images[0] ?? null;
  const selectedResult =
    result?.result.images.find((image) => image.image_id === selectedView?.image_id) ?? null;

  useEffect(() => {
    if (localizationTask?.execution_status === "completed" && !result && !loading && !error) onLoad();
  }, [error, loading, localizationTask?.execution_status, onLoad, result]);

  const refreshSelected = useCallback(() => {
    onRefreshView(selectedView ? [selectedView.image_id] : null);
  }, [onRefreshView, selectedView]);

  return (
    <section className="workspace-section" aria-labelledby="localization-heading">
      <div className="workspace-section__heading">
        <div>
          <span className="eyebrow">器官定位</span>
          <h1 id="localization-heading">Anatomy Localization</h1>
          <p>bbox 坐标相对完整原图。缩放、平移和全屏只改变显示，不修改原始影像或医学结果。</p>
        </div>
        <Button disabled={!diagnoseTask || loading} onClick={onLoad}><Icon name="refresh" />刷新定位</Button>
      </div>

      {!diagnoseTask ? (
        <EmptyState icon="image" title="尚无诊断来源" description="Localization 必须通过 source_task_id 关联一个 Diagnose Task。" />
      ) : !localizationTask && !current ? (
        <EmptyState icon="image" title="暂无定位任务" description="请在检查流程中创建 Anatomy Localization Task。" />
      ) : loading ? (
        <LoadingState label="正在读取定位结果、展示票据和图例" />
      ) : error ? (
        <ErrorNotice message={error} onRetry={onLoad} />
      ) : !result || !view || !legend ? (
        <EmptyState icon="image" title="定位结果尚不可展示" description="任务可能仍在执行，或当前结果不可用。请刷新任务状态后重试。" action={<Button onClick={onLoad}>重新查询</Button>} />
      ) : (
        <div className="localization-layout">
          <aside className="localization-sidebar">
            <div className="image-selector">
              <h2>影像序列</h2>
              {view.images.map((image) => {
                const imageResult = result.result.images.find((item) => item.image_id === image.image_id);
                return (
                  <button
                    className={image.image_id === selectedView?.image_id ? "image-select image-select--active" : "image-select"}
                    key={image.image_id}
                    onClick={() => setSelectedImageId(image.image_id)}
                  >
                    <span>#{image.sequence_no}</span>
                    <div><strong>{image.projection}</strong><small>{imageResult?.organs.length ?? 0} 个定位框</small></div>
                    <Icon name="chevron" />
                  </button>
                );
              })}
            </div>
            <div className="history-compact">
              <h2>任务历史</h2>
              {history.length === 0 ? <p>暂无历史记录</p> : history.map((item) => (
                <button key={item.task_id} onClick={() => onSelectHistory(item.task_id)}>
                  <span>{formatDateTime(item.created_at)}</span>
                  <StatusBadge status={item.execution_status} />
                </button>
              ))}
            </div>
          </aside>
          <main>
            {selectedView ? (
              <LocalizationViewer
                key={selectedView.image_id}
                viewImage={selectedView}
                resultImage={selectedResult}
                legend={legend}
                onExpired={refreshSelected}
              />
            ) : null}
            {selectedResult?.status === "not_localized" ? (
              <div className="notice notice--warning">
                <div><strong>本张影像未定位</strong><p>{selectedResult.reason_code ?? "证据不足"}</p></div>
              </div>
            ) : null}
          </main>
        </div>
      )}
    </section>
  );
}
