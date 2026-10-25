"use client";

import { Activity, Coins, Cpu, Route } from "lucide-react";
import { useEffect, useState } from "react";
import { TracePanel } from "@/components/TracePanel";
import { Card, CardHeader, Empty } from "@/components/ui";
import { get } from "@/lib/api";
import type { RunSummary, Savings, Status } from "@/lib/types";
import { cn, compact, ms, TIER_STYLE, usd } from "@/lib/utils";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [stats, setStats] = useState<Savings | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [selected, setSelected] = useState<RunSummary | null>(null);

  useEffect(() => {
    get<RunSummary[]>("/api/traces").then((r) => {
      setRuns(r);
      setSelected(r[0] ?? null);
    }).catch(() => {});
    get<Savings>("/api/stats").then(setStats).catch(() => {});
    get<Status>("/api/status").then(setStatus).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-fg">Runs &amp; routing</h1>
        <p className="mt-1 text-sm text-fg-muted">
          Each agent task goes to the cheapest Nemotron tier that handles it well. These numbers are measured on every
          real run, not estimated.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat icon={<Route className="size-4" />} label="Saved vs. Ultra-only" value={`${stats?.saved_pct ?? 0}%`} accent />
        <Stat icon={<Coins className="size-4" />} label="Actual spend" value={usd(stats?.actual_usd)} />
        <Stat icon={<Coins className="size-4" />} label="Same tokens on Ultra" value={usd(stats?.ultra_only_usd)} />
        <Stat
          icon={<Cpu className="size-4" />}
          label="Calls by tier"
          value={Object.entries(stats?.calls_by_tier ?? {}).map(([t, n]) => `${t[0].toUpperCase()}${n}`).join(" · ") || "–"}
        />
      </div>

      {status && (
        <Card>
          <CardHeader icon={<Route className="size-4" />} title="Routing table" subtitle="Model IDs come from Token Factory's /v1/models" />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left text-sm">
              <thead className="bg-muted text-xs uppercase tracking-wide text-fg-subtle">
                <tr>
                  <th className="px-4 py-2 font-medium">Task</th>
                  <th className="px-4 py-2 font-medium">Tier</th>
                  <th className="px-4 py-2 font-medium">Why</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(status.routes).map(([task, r]) => (
                  <tr key={task}>
                    <td className="px-4 py-2 font-mono text-xs text-fg">{task}</td>
                    <td className="px-4 py-2">
                      <span className={cn("rounded px-1.5 py-px text-[10px] font-semibold uppercase ring-1 ring-inset", TIER_STYLE[r.tier])}>{r.tier}</span>
                      <span className="ml-2 font-mono text-[11px] text-fg-subtle">{status.models[r.tier]}</span>
                    </td>
                    <td className="px-4 py-2 text-fg-muted">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader icon={<Activity className="size-4" />} title="Recent runs" />
          {runs.length === 0 ? (
            <Empty title="No runs yet">Run discovery, eligibility, or drafting and the runs will show up here.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {runs.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => setSelected(r)}
                    className={cn("flex w-full items-center gap-4 px-5 py-3 text-left text-sm hover:bg-muted", selected?.id === r.id && "bg-muted")}
                  >
                    <span className="w-24 font-medium capitalize text-fg">{r.label.split(":")[0]}</span>
                    <span className="flex-1 text-xs text-fg-muted">
                      {r.llm_calls} model calls · {r.tool_calls} searches · {compact(r.prompt_tokens + r.completion_tokens)} tokens
                    </span>
                    <span className="w-16 text-right text-xs tabular-nums text-fg-muted">{ms(r.duration_ms)}</span>
                    <span className="w-14 text-right text-xs font-medium tabular-nums text-emerald-600">−{r.savings.saved_pct}%</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        {selected && (
          <TracePanel events={selected.events ?? []} summary={selected} running={false} className="h-[560px]" />
        )}
      </div>
    </div>
  );
}

function Stat({ icon, label, value, accent }: { icon: React.ReactNode; label: string; value: string; accent?: boolean }) {
  return (
    <Card className="px-4 py-3">
      <p className="flex items-center gap-1.5 text-xs text-fg-muted">{icon} {label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", accent ? "text-emerald-600" : "text-fg")}>{value}</p>
    </Card>
  );
}
