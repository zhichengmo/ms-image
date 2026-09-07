import type { ButtonHTMLAttributes, ReactNode, SVGProps } from "react";

import type { TaskExecutionStatus } from "../types/runtime";

export type IconName =
  | "activity"
  | "arrow"
  | "check"
  | "chevron"
  | "close"
  | "expand"
  | "eye"
  | "file"
  | "image"
  | "minus"
  | "plus"
  | "refresh"
  | "report"
  | "shield"
  | "upload";

const paths: Record<IconName, ReactNode> = {
  activity: <path d="M3 12h4l2-7 4 14 2-7h6" />,
  arrow: <path d="m9 18 6-6-6-6" />,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  close: <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>,
  expand: <><path d="M8 3H3v5" /><path d="m3 3 6 6" /><path d="M16 21h5v-5" /><path d="m21 21-6-6" /></>,
  eye: <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></>,
  file: <><path d="M6 2h8l4 4v16H6z" /><path d="M14 2v5h5" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="2" /><path d="m3 17 5-5 4 4 3-3 6 5" /></>,
  minus: <path d="M5 12h14" />,
  plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>,
  report: <><path d="M5 3h14v18H5z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
  shield: <><path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5z" /><path d="m9 12 2 2 4-5" /></>,
  upload: <><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M4 20h16" /></>,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}

export function Button({
  tone = "default",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "default" | "primary" | "danger" | "ghost";
}) {
  return (
    <button className={`button button--${tone} ${className}`} {...props}>
      {children}
    </button>
  );
}

const statusLabels: Record<string, string> = {
  pending: "待处理",
  queued: "已排队",
  running: "处理中",
  retry_wait: "等待重试",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  dead_letter: "异常终止",
  uploading: "待上传",
  hashing: "正在校验文件",
  validating: "影像校验中",
  ready: "影像就绪",
  preparing: "准备中",
};

export function StatusBadge({ status }: { status: TaskExecutionStatus | string }) {
  const tone =
    status === "completed" || status === "ready"
      ? "success"
      : ["failed", "dead_letter", "quarantined"].includes(status)
        ? "danger"
        : status === "cancelled"
          ? "muted"
          : ["running", "validating", "hashing", "preparing"].includes(status)
            ? "active"
            : "warning";
  return <span className={`status status--${tone}`}>{statusLabels[status] ?? status}</span>;
}

export function EmptyState({
  title,
  description,
  icon = "file",
  action,
}: {
  title: string;
  description: string;
  icon?: IconName;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon"><Icon name={icon} /></span>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="notice notice--error" role="alert">
      <div>
        <strong>操作未完成</strong>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <Button tone="ghost" onClick={onRetry}>
          <Icon name="refresh" />重试
        </Button>
      ) : null}
    </div>
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

// Shared formatter intentionally lives with the small presentational primitives.
// eslint-disable-next-line react-refresh/only-export-components
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
}
