import type { QualityReviewResponse, TaskResponse } from "../types/runtime";
import { Button, formatDateTime, Icon, StatusBadge } from "./ui";

interface TaskCardProps {
  index: string;
  title: string;
  description: string;
  task: TaskResponse | null;
  enabled: boolean;
  busy: boolean;
  cta: string;
  onCreate: () => void;
  onCancel: (task: TaskResponse) => void;
}

function TaskCard({
  index,
  title,
  description,
  task,
  enabled,
  busy,
  cta,
  onCreate,
  onCancel,
}: TaskCardProps) {
  const active = task && ["pending", "queued", "running", "retry_wait"].includes(task.execution_status);
  return (
    <article className="task-card">
      <div className="task-card__head">
        <span className="task-card__number">{index}</span>
        {task ? <StatusBadge status={task.execution_status} /> : <span className="status status--muted">未创建</span>}
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {task ? (
        <dl className="task-card__meta">
          <div><dt>Task ID</dt><dd title={task.id}>{task.id.slice(0, 12)}…</dd></div>
          <div><dt>医学状态</dt><dd>{task.ai_medical_status}</dd></div>
          <div><dt>更新时间</dt><dd>{formatDateTime(task.updated_at)}</dd></div>
          {task.next_retry_at ? <div><dt>下次重试</dt><dd>{formatDateTime(task.next_retry_at)}</dd></div> : null}
        </dl>
      ) : null}
      {task?.error_code ? <p className="task-error" role="alert">{task.error_code}</p> : null}
      <div className="task-card__actions">
        {!task ? (
          <Button tone="default" disabled={!enabled || busy} onClick={onCreate}>
            <Icon name="activity" />{cta}
          </Button>
        ) : null}
        {active ? (
          <Button tone="danger" disabled={busy} onClick={() => onCancel(task)}>
            <Icon name="close" />取消任务
          </Button>
        ) : null}
      </div>
    </article>
  );
}

interface TaskBoardProps {
  studyReady: boolean;
  qualityTask: TaskResponse | null;
  diagnoseTask: TaskResponse | null;
  localizationTask: TaskResponse | null;
  qualityResult: QualityReviewResponse | null;
  busy: boolean;
  onCreateQuality: () => void;
  onCreateDiagnose: () => void;
  onCreateLocalization: () => void;
  onCancel: (kind: "quality" | "diagnose" | "localization", task: TaskResponse) => void;
}

export function TaskBoard(props: TaskBoardProps) {
  return (
    <section className="panel task-board" aria-labelledby="task-heading">
      <div className="panel__heading">
        <div>
          <span className="eyebrow">02 · AI 任务</span>
          <h2 id="task-heading">任务执行状态</h2>
          <p>Quality 完成后创建 Diagnose，并立即以其 Task ID 启动 Localization；两条链路独立并行执行。</p>
        </div>
        <span className="assistive-label"><Icon name="shield" />AI 辅助结果</span>
      </div>
      <div className="task-grid">
        <TaskCard
          index="A"
          title="Quality Review"
          description="逐图核对 X-Ray 有效性、部位、观察投照位与基础质量。"
          task={props.qualityTask}
          enabled={props.studyReady}
          busy={props.busy}
          cta="开始质量审查"
          onCreate={props.onCreateQuality}
          onCancel={(task) => props.onCancel("quality", task)}
        />
        <TaskCard
          index="B"
          title="Diagnose"
          description="引用已完成的 Quality Task，生成当前诊断报告。"
          task={props.diagnoseTask}
          enabled={props.qualityTask?.execution_status === "completed"}
          busy={props.busy}
          cta="并行启动诊断与定位"
          onCreate={props.onCreateDiagnose}
          onCancel={(task) => props.onCancel("diagnose", task)}
        />
        <TaskCard
          index="C"
          title="Anatomy Localization"
          description="通过 source_task_id 关联已创建的 Diagnose Task，与诊断主链并行生成原图器官 bbox。"
          task={props.localizationTask}
          enabled={Boolean(props.diagnoseTask)}
          busy={props.busy}
          cta="开始器官定位"
          onCreate={props.onCreateLocalization}
          onCancel={(task) => props.onCancel("localization", task)}
        />
      </div>

      {props.qualityResult ? (
        <div className="quality-strip">
          <div className="quality-strip__heading">
            <strong>质量审查结果</strong>
            <span>{props.qualityResult.result.images.length} 张影像</span>
          </div>
          <div className="quality-list">
            {props.qualityResult.result.images.map((image) => (
              <article key={image.image_id}>
                <span>#{image.sequence_no}</span>
                <strong>{image.primary_body_part || "未识别部位"}</strong>
                <small>观察体位：{image.observed_projection || "未确定"}</small>
                <StatusBadge status={image.quality_status} />
                {image.projection_consistency === "inconsistent" ? (
                  <small>体位冲突：申报 {image.declared_projection}，需人工复核</small>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
