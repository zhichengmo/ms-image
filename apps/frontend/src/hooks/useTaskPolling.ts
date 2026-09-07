import { useEffect, useRef } from "react";

import { RuntimeApi } from "../lib/api";
import { isTaskActive } from "../state/workflow";
import type { TaskResponse } from "../types/runtime";

interface PollTarget {
  key: "quality" | "diagnose" | "localization";
  task: TaskResponse | null;
}

interface UseTaskPollingOptions {
  api: RuntimeApi | null;
  targets: PollTarget[];
  retryKey?: number;
  onTask: (key: PollTarget["key"], task: TaskResponse) => void;
  onError: (key: PollTarget["key"], message: string) => void;
  onRecovered?: (key: PollTarget["key"]) => void;
}

function nextDelay(task: TaskResponse): number {
  if (task.execution_status === "retry_wait" && task.next_retry_at) {
    return Math.max(1_000, Math.min(30_000, Date.parse(task.next_retry_at) - Date.now()));
  }
  return 2_000;
}

export function useTaskPolling({
  api,
  targets,
  retryKey = 0,
  onTask,
  onError,
  onRecovered,
}: UseTaskPollingOptions): void {
  const callbacks = useRef({ onTask, onError, onRecovered });
  callbacks.current = { onTask, onError, onRecovered };
  const signature = targets
    .map(({ key, task }) => `${key}:${task?.id ?? ""}:${task?.execution_status ?? ""}`)
    .join("|");

  useEffect(() => {
    if (!api) return;
    const controllers: AbortController[] = [];
    const timers: number[] = [];

    for (const target of targets) {
      if (!isTaskActive(target.task)) continue;
      const controller = new AbortController();
      controllers.push(controller);
      let attempts = 0;
      let consecutiveFailures = 0;

      const poll = async () => {
        if (controller.signal.aborted || !target.task) return;
        attempts += 1;
        if (attempts > 180) {
          callbacks.current.onError(
            target.key,
            `${target.key} Task 轮询已达到上限，请手动刷新。`,
          );
          return;
        }
        try {
          const task = await api.getTask(target.task.id);
          if (controller.signal.aborted) return;
          if (consecutiveFailures > 0) callbacks.current.onRecovered?.(target.key);
          consecutiveFailures = 0;
          callbacks.current.onTask(target.key, task);
          if (isTaskActive(task)) {
            timers.push(window.setTimeout(poll, nextDelay(task)));
          }
        } catch (error) {
          if (controller.signal.aborted) return;
          consecutiveFailures += 1;
          callbacks.current.onError(
            target.key,
            error instanceof Error ? error.message : `${target.key} Task 查询失败`,
          );
          if (attempts <= 180) {
            const retryDelay = Math.min(
              30_000,
              1_000 * 2 ** Math.min(consecutiveFailures - 1, 5),
            );
            timers.push(window.setTimeout(poll, retryDelay));
          }
        }
      };

      timers.push(window.setTimeout(poll, nextDelay(target.task!)));
    }

    return () => {
      controllers.forEach((controller) => controller.abort());
      timers.forEach((timer) => window.clearTimeout(timer));
    };
    // signature intentionally represents the serializable polling targets.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, retryKey, signature]);
}
