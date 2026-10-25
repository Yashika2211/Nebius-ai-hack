"use client";

import { useCallback, useRef, useState } from "react";
import { stream } from "./api";
import type { RunSummary, TraceEvent } from "./types";

export interface AgentRun<T> {
  running: boolean;
  events: TraceEvent[];
  tokens: string;
  result: T | null;
  summary: RunSummary | null;
  error: string | null;
  start: (path: string, body?: unknown) => Promise<T | null>;
  reset: () => void;
}

/** Drive a streaming agent endpoint and collect its trace, tokens, and result. */
export function useAgentRun<T>(): AgentRun<T> {
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [tokens, setTokens] = useState("");
  const [result, setResult] = useState<T | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abort.current?.abort();
    setEvents([]);
    setTokens("");
    setResult(null);
    setSummary(null);
    setError(null);
    setRunning(false);
  }, []);

  const start = useCallback(async (path: string, body?: unknown) => {
    reset();
    const controller = new AbortController();
    abort.current = controller;
    setRunning(true);
    let final: T | null = null;
    try {
      await stream(
        path,
        body,
        (m) => {
          if (m.type === "trace") setEvents((prev) => [...prev, m.event]);
          else if (m.type === "token") setTokens((prev) => prev + m.text);
          else if (m.type === "result") {
            final = m.result as T;
            setResult(final);
          } else if (m.type === "done") setSummary(m.summary);
          else if (m.type === "error") setError(m.error);
        },
        controller.signal,
      );
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
    return final;
  }, [reset]);

  return { running, events, tokens, result, summary, error, start, reset };
}
