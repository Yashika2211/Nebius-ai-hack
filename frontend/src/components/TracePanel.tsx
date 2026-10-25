"use client";

import { Activity, CheckCircle2, Cpu, Database, Globe, Loader2, TriangleAlert, Zap } from "lucide-react";
import { useEffect, useRef } from "react";
import type { RunSummary, TraceEvent } from "@/lib/types";
import { cn, compact, ms, TIER_STYLE, usd } from "@/lib/utils";

/** Live agent trace: each step, which Nemotron model ran it, latency, tokens, and cost. */
export function TracePanel({
  events,
  summary,
  running,
  className,
}: {
  events: TraceEvent[];
  summary: RunSummary | null;
  running: boolean;
  className?: string;
}) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Scroll only the panel, never the page.
    const el = list.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  const llm = events.filter((e) => e.kind === "llm");
  const live = liveSavings(llm);

  return (
    <div className={cn("flex min-h-0 flex-col rounded-xl bg-surface ring-1 ring-border shadow-sm", className)}>
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-fg">
          <Activity className="size-4 text-brand" /> Agent trace
        </div>
        {running ? (
          <span className="flex items-center gap-1.5 text-xs text-fg-muted">
            <Loader2 className="size-3 animate-spin" /> running
          </span>
        ) : summary ? (
          <span className="text-xs text-fg-muted">{ms(summary.duration_ms)} total</span>
        ) : null}
      </div>

      <div ref={list} className="min-h-0 flex-1 overflow-y-auto px-2 py-2 text-xs">
        {events.length === 0 && !running && (
          <p className="px-2 py-6 text-center text-fg-subtle">Run an agent step to see every model call here.</p>
        )}
        {events.map((e) => (
          <TraceRow key={e.seq} e={e} />
        ))}
      </div>

      {llm.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-fg-muted">Routing saved vs. Ultra-only</span>
            <span className="text-lg font-semibold tabular-nums text-emerald-600">
              {(summary?.savings.saved_pct ?? live.pct).toFixed(1)}%
            </span>
          </div>
          <div className="mt-1 flex justify-between text-[11px] tabular-nums text-fg-subtle">
            <span>
              {usd(summary?.savings.actual_usd ?? live.actual)} actual · {usd(summary?.savings.ultra_only_usd ?? live.baseline)} on Ultra
            </span>
            <span>{compact(llm.reduce((s, e) => s + (e.prompt_tokens ?? 0) + (e.completion_tokens ?? 0), 0))} tokens</span>
          </div>
          <TierBar llm={llm} />
        </div>
      )}
    </div>
  );
}

// Matches backend defaults; only used for the live number before the run's summary arrives.
const ULTRA = { in: 1.0, out: 3.0 };

function liveSavings(llm: TraceEvent[]) {
  const actual = llm.reduce((s, e) => s + (e.cost ?? 0), 0);
  const baseline = llm.reduce(
    (s, e) => s + ((e.prompt_tokens ?? 0) * ULTRA.in + (e.completion_tokens ?? 0) * ULTRA.out) / 1e6,
    0,
  );
  return { actual, baseline, pct: baseline ? (1 - actual / baseline) * 100 : 0 };
}

function TierBar({ llm }: { llm: TraceEvent[] }) {
  const counts = { nano: 0, super: 0, ultra: 0 } as Record<string, number>;
  llm.forEach((e) => e.tier && (counts[e.tier] += 1));
  const total = llm.length || 1;
  const colors: Record<string, string> = { nano: "bg-emerald-500", super: "bg-sky-500", ultra: "bg-violet-500" };
  return (
    <div className="mt-2">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-muted">
        {Object.entries(counts).map(([t, n]) => (
          <div key={t} className={colors[t]} style={{ width: `${(n / total) * 100}%` }} />
        ))}
      </div>
      <div className="mt-1.5 flex gap-3 text-[11px] text-fg-subtle">
        {Object.entries(counts).map(([t, n]) => (
          <span key={t} className="flex items-center gap-1">
            <span className={cn("size-1.5 rounded-full", colors[t])} /> {t} {n}
          </span>
        ))}
      </div>
    </div>
  );
}

function TraceRow({ e }: { e: TraceEvent }) {
  if (e.kind === "step") {
    return (
      <div className="mt-2 flex items-center gap-2 px-2 pb-1 pt-1.5 first:mt-0">
        <Zap className="size-3 text-brand" />
        <span className="font-semibold text-fg">{e.name}</span>
        {e.detail && <span className="truncate text-fg-subtle">{e.detail}</span>}
      </div>
    );
  }
  if (e.kind === "check" || e.kind === "note") {
    return (
      <div className="flex items-start gap-2 rounded-md px-2 py-1 text-fg-muted">
        <CheckCircle2 className="mt-px size-3 shrink-0 text-emerald-600" />
        <span>{e.detail}</span>
      </div>
    );
  }
  const isLLM = e.kind === "llm";
  const failed = e.status === "error";
  return (
    <div
      className={cn("group rounded-md px-2 py-1.5 hover:bg-muted", failed && "bg-rose-50 dark:bg-rose-500/10")}
      title={isLLM ? `${e.model}\n${e.reason ?? ""}` : e.detail}
    >
      <div className="flex items-center gap-2">
        {failed ? (
          <TriangleAlert className="size-3 shrink-0 text-rose-600" />
        ) : isLLM ? (
          <Cpu className="size-3 shrink-0 text-fg-subtle" />
        ) : (
          <Globe className="size-3 shrink-0 text-fg-subtle" />
        )}
        <span className="truncate font-mono text-[11px] text-fg">{isLLM ? e.task : e.tool}</span>
        {isLLM && e.tier && (
          <span className={cn("rounded px-1.5 py-px text-[10px] font-semibold uppercase ring-1 ring-inset", TIER_STYLE[e.tier])}>
            {e.tier}
          </span>
        )}
        {e.cached && (
          <span className="flex items-center gap-0.5 text-[10px] text-fg-subtle" title="Served from cache">
            <Database className="size-2.5" /> cache
          </span>
        )}
        <span className="ml-auto shrink-0 tabular-nums text-fg-subtle">{ms(e.latency_ms)}</span>
      </div>
      <div className="mt-0.5 flex gap-3 pl-5 text-[11px] tabular-nums text-fg-subtle">
        {isLLM ? (
          <>
            <span>{compact(e.prompt_tokens)} in / {compact(e.completion_tokens)} out</span>
            <span>{usd(e.cost)}</span>
            <span className="hidden truncate group-hover:inline">{e.reason}</span>
          </>
        ) : (
          <span className="truncate">{e.detail}{e.results !== undefined ? ` · ${e.results} results` : ""}</span>
        )}
      </div>
      {failed && <div className="mt-0.5 pl-5 text-[11px] text-rose-700 dark:text-rose-300">{e.error}</div>}
    </div>
  );
}
