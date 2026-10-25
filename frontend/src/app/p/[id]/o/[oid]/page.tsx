"use client";

import { ArrowLeft, Building, CalendarClock, ExternalLink, FileText, Gauge, MapPin, ShieldCheck, Tag } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { DraftBody, DraftView } from "@/components/DraftView";
import { EligibilityView } from "@/components/EligibilityView";
import { bandLabel, FitBreakdown, FitRing } from "@/components/FitScore";
import { TracePanel } from "@/components/TracePanel";
import { Badge, Button, Card, Empty, ErrorNote } from "@/components/ui";
import { get } from "@/lib/api";
import type { Draft, Eligibility, Opportunity } from "@/lib/types";
import { useAgentRun } from "@/lib/useAgentRun";
import { cn, dueLabel } from "@/lib/utils";

type Tab = "fit" | "eligibility" | "draft";

export default function OpportunityPage({ params }: { params: Promise<{ id: string; oid: string }> }) {
  const { id, oid } = use(params);
  const [opp, setOpp] = useState<Opportunity | null>(null);
  const [tab, setTab] = useState<Tab>("fit");
  const [error, setError] = useState<string | null>(null);
  const elig = useAgentRun<Eligibility>();
  const draft = useAgentRun<Draft>();

  useEffect(() => {
    get<Opportunity>(`/api/opportunities/${oid}`).then(setOpp).catch((e) => setError(String(e)));
  }, [oid]);

  const eligibility = elig.result ?? opp?.eligibility ?? null;
  const draftData = draft.result ?? opp?.draft ?? null;
  const active = tab === "draft" || draft.running ? draft : elig;

  async function runEligibility() {
    setTab("eligibility");
    await elig.start(`/api/profiles/${id}/opportunities/${oid}/eligibility`);
  }

  async function runDraft() {
    setTab("draft");
    await draft.start(`/api/profiles/${id}/opportunities/${oid}/draft`);
  }

  if (error) return <ErrorNote message={error} />;
  if (!opp) return <Card className="h-64 animate-pulse" />;

  return (
    <div className="space-y-6">
      <Link href={`/p/${id}`} className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg">
        <ArrowLeft className="size-4" /> All opportunities
      </Link>

      <Card className="p-5">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
          <FitRing score={opp.fit.score} band={opp.fit.band} size={76} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={opp.fit.band === "strong" ? "good" : opp.fit.band === "possible" ? "warn" : "bad"}>{bandLabel(opp.fit.band)}</Badge>
              {opp.type && <Badge>{opp.type}</Badge>}
              {opp.solicitation_number && <Badge className="font-mono">{opp.solicitation_number}</Badge>}
            </div>
            <h1 className="mt-2 text-xl font-semibold leading-snug text-fg">{opp.title}</h1>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-fg-muted">
              {opp.agency && <span className="flex items-center gap-1"><Building className="size-3.5" /> {opp.agency}</span>}
              <span className="flex items-center gap-1"><CalendarClock className="size-3.5" /> {dueLabel(opp.days_left, opp.due_date)}{opp.due_date ? ` (${opp.due_date})` : ""}</span>
              {opp.set_aside && <span className="flex items-center gap-1"><Tag className="size-3.5" /> {opp.set_aside}</span>}
              {opp.place_of_performance && <span className="flex items-center gap-1"><MapPin className="size-3.5" /> {opp.place_of_performance}</span>}
            </div>
            {opp.summary && <p className="mt-3 text-sm leading-relaxed text-fg-muted">{opp.summary}</p>}
            <a href={opp.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline">
              View original solicitation <ExternalLink className="size-3.5" />
            </a>
          </div>
          <div className="flex shrink-0 gap-2 sm:flex-col">
            <Button onClick={runEligibility} loading={elig.running} variant={eligibility ? "secondary" : "primary"}>
              <ShieldCheck className="size-4" /> {eligibility ? "Re-check eligibility" : "Check eligibility"}
            </Button>
            <Button onClick={runDraft} loading={draft.running} variant={draftData ? "secondary" : "primary"}>
              <FileText className="size-4" /> {draftData ? "Regenerate draft" : "Draft response"}
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0">
          <div className="mb-4 flex gap-1 rounded-lg bg-muted p-1 text-sm">
            {([
              ["fit", "Fit score", Gauge],
              ["eligibility", "Eligibility & risk", ShieldCheck],
              ["draft", "Compliance & draft", FileText],
            ] as const).map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition",
                  tab === key ? "bg-surface text-fg shadow-sm" : "text-fg-muted hover:text-fg",
                )}
              >
                <Icon className="size-4" /> <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>

          <Card className="p-5">
            {tab === "fit" && (
              <>
                <p className="text-sm text-fg-muted">
                  Nemotron Ultra scores each factor and cites the evidence. The weights are fixed in code, so the score
                  is reproducible, and any factor without verified evidence counts at half weight.
                </p>
                <FitBreakdown fit={opp.fit} />
              </>
            )}

            {tab === "eligibility" && (
              <>
                {elig.error && <ErrorNote message={elig.error} />}
                {eligibility ? (
                  <EligibilityView data={eligibility} />
                ) : elig.running ? (
                  <Empty title="Checking requirements…">Nemotron Super extracts the requirements, then Ultra decides whether you meet each one.</Empty>
                ) : (
                  <Empty icon={<ShieldCheck className="size-8" />} title="Eligibility not checked yet">
                    <Button className="mt-3" onClick={runEligibility}>Check eligibility</Button>
                  </Empty>
                )}
              </>
            )}

            {tab === "draft" && (
              <>
                {draft.error && <ErrorNote message={draft.error} />}
                {draft.running ? (
                  draft.tokens ? (
                    <div>
                      <p className="mb-2 text-xs font-medium text-brand">Streaming from Nemotron Super…</p>
                      <DraftBody text={draft.tokens} />
                    </div>
                  ) : (
                    <Empty title="Building the compliance matrix…">Mapping every “shall” statement in the RFP to a response section.</Empty>
                  )
                ) : draftData ? (
                  <DraftView data={draftData} title={opp.title} />
                ) : (
                  <Empty icon={<FileText className="size-8" />} title="No draft yet">
                    <Button className="mt-3" onClick={runDraft}>Draft response</Button>
                  </Empty>
                )}
              </>
            )}
          </Card>
        </div>

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
