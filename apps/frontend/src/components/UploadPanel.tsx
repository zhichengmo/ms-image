import { useMemo, useState } from "react";

import { formatBytes } from "../lib/fileMetadata";
import type { PersistedImageState, WorkflowState } from "../state/workflow";
import type { Species } from "../types/runtime";
import { Button, Icon, StatusBadge } from "./ui";

export interface UploadSlot {
  sequenceNo: number;
  file: File | null;
  projection: string;
}

interface UploadPanelProps {
  workflow: WorkflowState;
  busy: boolean;
  onDetailsChange: (patch: Partial<WorkflowState>) => void;
  onUpload: (slots: UploadSlot[]) => void;
}

const projectionOptions = [
  { value: "lateral", label: "侧位（未指定左右）" },
  { value: "right_lateral", label: "右侧位" },
  { value: "left_lateral", label: "左侧位" },
  { value: "ventrodorsal", label: "腹背位 VD" },
  { value: "dorsoventral", label: "背腹位 DV" },
  { value: "anteroposterior", label: "前后位 AP" },
  { value: "posteroanterior", label: "后前位 PA" },
];

function createSlots(count: number, existing: PersistedImageState[]): UploadSlot[] {
  return Array.from({ length: count }, (_, index) => ({
    sequenceNo: index + 1,
    file: null,
    projection: existing[index]?.projection ?? (index % 2 === 0 ? "lateral" : "ventrodorsal"),
  }));
}

export function UploadPanel({
  workflow,
  busy,
  onDetailsChange,
  onUpload,
}: UploadPanelProps) {
  const initialCount = Math.max(2, Math.min(5, workflow.images.length || 2));
  const [count, setCount] = useState(initialCount);
  const [slots, setSlots] = useState<UploadSlot[]>(() =>
    createSlots(initialCount, workflow.images),
  );

  const readyCount = workflow.images.filter(
    (image) => image.sequenceNo <= count && image.status === "ready",
  ).length;
  const hasStarted = Boolean(workflow.sessionStartedAt || workflow.sessionId);
  const studyReady = workflow.studyStatus === "ready";
  const canReconcileRemoteImages = Boolean(workflow.seriesId);
  const canSubmit = useMemo(
    () =>
      slots.length >= 2 &&
      slots.length <= 5 &&
      slots.every((slot) => {
        const persisted = workflow.images.find(
          (image) => image.sequenceNo === slot.sequenceNo,
        );
        return Boolean(slot.file) || Boolean(
          persisted?.imageId && ["ready", "validating"].includes(persisted.status),
        ) || canReconcileRemoteImages;
      }) &&
      workflow.subjectId.trim().length > 0 &&
      workflow.caseKey.trim().length > 0,
    [canReconcileRemoteImages, slots, workflow.caseKey, workflow.images, workflow.subjectId],
  );

  const updateCount = (nextCount: number) => {
    setCount(nextCount);
    setSlots((current) =>
      Array.from({ length: nextCount }, (_, index) =>
        current[index] ?? {
          sequenceNo: index + 1,
          file: null,
          projection: index % 2 === 0 ? "lateral" : "ventrodorsal",
        },
      ),
    );
  };

  const updateSlot = (index: number, patch: Partial<UploadSlot>) => {
    setSlots((current) =>
      current.map((slot, slotIndex) =>
        slotIndex === index ? { ...slot, ...patch } : slot,
      ),
    );
  };

  return (
    <section className="panel upload-panel" aria-labelledby="case-heading">
      <div className="panel__heading">
        <div>
          <span className="eyebrow">01 · 影像准备</span>
          <h2 id="case-heading">新建 X-Ray 检查</h2>
          <p>录入病例标识并上传 2–5 张原始影像。投照位是调用方事实，请按实际影像选择。</p>
        </div>
        {workflow.studyId ? (
          <div className="record-id" title={workflow.studyId}>
            <span>Study</span>
            <code>{workflow.studyId.slice(0, 12)}…</code>
          </div>
        ) : null}
      </div>

      <div className="case-form">
        <label className="field">
          <span>主体标识</span>
          <input
            autoComplete="off"
            disabled={hasStarted}
            maxLength={128}
            placeholder="例如 PET-2026-001"
            value={workflow.subjectId}
            onChange={(event) => onDetailsChange({ subjectId: event.target.value })}
          />
        </label>
        <label className="field">
          <span>病例键</span>
          <input
            autoComplete="off"
            disabled={hasStarted}
            maxLength={128}
            placeholder="例如 CASE-001"
            value={workflow.caseKey}
            onChange={(event) => onDetailsChange({ caseKey: event.target.value })}
          />
        </label>
        <label className="field">
          <span>物种</span>
          <select
            disabled={hasStarted}
            value={workflow.species}
            onChange={(event) =>
              onDetailsChange({ species: event.target.value as Species })
            }
          >
            <option value="cat">猫</option>
            <option value="dog">犬</option>
          </select>
        </label>
        <label className="field">
          <span>影像数量</span>
          <select
            disabled={hasStarted}
            value={count}
            onChange={(event) => updateCount(Number(event.target.value))}
          >
            {[2, 3, 4, 5].map((value) => (
              <option key={value} value={value}>{value} 张</option>
            ))}
          </select>
        </label>
        <label className="field field--wide">
          <span>主诉</span>
          <input
            maxLength={500}
            placeholder="简要描述症状；仅用于诊断任务"
            value={workflow.chiefComplaint}
            onChange={(event) => onDetailsChange({ chiefComplaint: event.target.value })}
          />
        </label>
        <label className="field field--wide">
          <span>检查目的</span>
          <input
            maxLength={500}
            value={workflow.studyReason}
            onChange={(event) => onDetailsChange({ studyReason: event.target.value })}
          />
        </label>
      </div>

      <div className="image-slots" aria-label="影像上传槽位">
        {slots.map((slot, index) => {
          const persisted = workflow.images.find(
            (image) => image.sequenceNo === slot.sequenceNo,
          );
          return (
            <article className="image-slot" key={slot.sequenceNo}>
              <div className="image-slot__index">{String(slot.sequenceNo).padStart(2, "0")}</div>
              <div className="image-slot__body">
                <div className="image-slot__topline">
                  <label className="file-trigger">
                    <Icon name="upload" />
                    <span>{slot.file ? "更换文件" : persisted?.imageId ? "重新选择" : "选择影像"}</span>
                    <input
                      accept=".jpg,.jpeg,.png,.dcm,.dicom,image/jpeg,image/png,application/dicom"
                      disabled={busy || persisted?.status === "ready"}
                      type="file"
                      onChange={(event) =>
                        updateSlot(index, { file: event.target.files?.[0] ?? null })
                      }
                    />
                  </label>
                  {persisted ? <StatusBadge status={persisted.status} /> : null}
                </div>
                <div className="image-slot__filename">
                  <strong>{slot.file?.name ?? persisted?.name ?? "尚未选择文件"}</strong>
                  <span>{slot.file ? formatBytes(slot.file.size) : "JPEG / PNG / DICOM"}</span>
                </div>
                <label className="field field--compact">
                  <span>投照位</span>
                  <select
                    disabled={busy || Boolean(persisted?.imageId)}
                    value={slot.projection}
                    onChange={(event) => updateSlot(index, { projection: event.target.value })}
                  >
                    {projectionOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                {persisted?.errorCode ? (
                  <p className="field-error" role="alert">{persisted.errorCode}</p>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>

      <div className="panel__footer">
        <div className="progress-summary">
          <span>{readyCount}/{count} 张已通过校验</span>
          <div className="progress-track" aria-hidden="true">
            <span style={{ width: `${(readyCount / count) * 100}%` }} />
          </div>
        </div>
        <Button
          tone="primary"
          disabled={busy || !canSubmit || studyReady}
          onClick={() => onUpload(slots)}
        >
          <Icon name="upload" />
          {busy
            ? "正在处理影像"
            : studyReady
              ? "检查已冻结"
              : workflow.studyId
                ? "继续上传并冻结"
                : "上传并冻结检查"}
        </Button>
      </div>
    </section>
  );
}
