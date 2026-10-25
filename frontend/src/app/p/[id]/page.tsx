"use client";

import { BellRing, Radar, Search } from "lucide-react";
import { use, useCallback, useEffect, useState } from "react";
import { OpportunityCard } from "@/components/OpportunityCard";
import { ProfileCard } from "@/components/ProfileCard";
import { TracePanel } from "@/components/TracePanel";
import { Button, Card, CardHeader, Empty, ErrorNote } from "@/components/ui";
import { get } from "@/lib/api";
import type { Opportunity, Profile } from "@/lib/types";
import { useAgentRun } from "@/lib/useAgentRun";

interface WatchRun {
  id: string;
  new_count: number;
  items: { id: string; title: string; score: number; due_date?: string }[];
  created_at: number;
}

export default function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [watchRuns, setWatchRuns] = useState<WatchRun[]>([]);
  const [query, setQuery] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const discover = useAgentRun<Opportunity[]>();
  const watch = useAgentRun<WatchRun["items"]>();

  const refresh = useCallback(() => {
    get<Opportunity[]>(`/api/profiles/${id}/opportunities`).then(setOpps).catch(() => {});
    get<WatchRun[]>(`/api/profiles/${id}/watch`).then(setWatchRuns).catch(() => {});
  }, [id]);

  useEffect(() => {
    get<Profile>(`/api/profiles/${id}`).then(setProfile).catch((e) => setLoadError(String(e)));
    refresh();
  }, [id, refresh]);

  async function runDiscover() {
    await discover.start(`/api/profiles/${id}/discover`, { query });
    refresh();
  }

  async function runWatch() {
    await watch.start(`/api/profiles/${id}/watch/run`);
    refresh();
  }

  const active = watch.running || (watch.events.length > 0 && !discover.running && discover.events.length === 0) ? watch : discover;
  const sorted = [...opps].sort((a, b) => (b.fit?.score ?? 0) - (a.fit?.score ?? 0));

  if (loadError) return <ErrorNote message={`Could not load company: ${loadError}`} />;

  return (
    <div className="grid gap-6 lg:grid-cols-[340px_1fr] xl:grid-cols-[340px_1fr_340px]">
      <div className="space-y-6">
        {profile ? <ProfileCard profile={profile} /> : <Card className="h-96 animate-pulse" />}
        <Card>
          <CardHeader
            icon={<BellRing className="size-4" />}
            title="Watch mode"
            subtitle="Re-scans every day and shows only new matches."
            action={<Button variant="secondary" onClick={runWatch} loading={watch.running} className="px-3 py-1.5 text-xs">Scan now</Button>}
          />
          <div className="px-5 py-3 text-sm">
            {watchRuns.length === 0 ? (
              <p className="text-xs text-fg-subtle">No scans yet. The daily scheduled job and “Scan now” both log here.</p>
            ) : (
              <ul className="space-y-2">
                {watchRuns.slice(0, 5).map((r) => (
                  <li key={r.id} className="flex items-center justify-between text-xs">
                    <span className="text-fg-muted">{new Date(r.created_at * 1000).toLocaleString()}</span>
                    <span className={r.new_count ? "font-medium text-brand" : "text-fg-subtle"}>
                      {r.new_count} new
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>

      <div className="min-w-0 space-y-4">
        <Card className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !discover.running && runDiscover()}
                placeholder="Optional focus, e.g. “clinic custodial Texas”"
                className="w-full rounded-lg bg-surface py-2 pl-9 pr-3 text-sm ring-1 ring-border placeholder:text-fg-subtle focus:outline-none focus:ring-2 focus:ring-brand"
              />
            </div>
            <Button onClick={runDiscover} loading={discover.running}>
              <Radar className="size-4" /> Find opportunities
            </Button>
          </div>
          <p className="mt-2 text-xs text-fg-subtle">
            Searches SAM.gov and state and city procurement portals. Nemotron Nano triages results, and Ultra scores the best matches.
          </p>
        </Card>

        {discover.error && <ErrorNote message={discover.error} />}

        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-fg">Ranked opportunities</h2>
          <span className="text-xs text-fg-subtle">{opps.length} saved</span>
        </div>

        {discover.running && opps.length === 0 && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => <Card key={i} className="h-28 animate-pulse" />)}
          </div>
        )}

        {sorted.length > 0 ? (
          <div className="space-y-3">
            {sorted.map((o) => <OpportunityCard key={o.id} opp={o} profileId={id} />)}
          </div>
        ) : (
          !discover.running && (
            <Card>
              <Empty icon={<Radar className="size-8" />} title="No opportunities yet">
                Click <b>Find opportunities</b> to search live solicitations that match this profile.
              </Empty>
            </Card>
          )
        )}
      </div>

      <div className="lg:col-span-2 xl:col-span-1">
        <TracePanel
          events={active.events}
          summary={active.summary}
          running={active.running}
          className="h-[520px] xl:sticky xl:top-20 xl:h-[calc(100vh-7rem)]"
        />
      </div>
    </div>
  );
}
