"use client";

import { AlertTriangle, CheckCircle2, ClipboardCopy, Download, FileWarning, ShieldCheck } from "lucide-react";
import { Fragment, useState } from "react";
import type { Draft, Evidence } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Citation, Citations, GroundedMark } from "./Citation";
import { Badge, Button } from "./ui";

const CITE = /\[((?:profile|rfp):\d+(?:\s*,\s*(?:profile|rfp):\d+)*)\]/g;

/** Render draft text with live citation chips; uncited spans stay plain text. */
function CitedText({ text, index }: { text: string; index: Record<string, Evidence> }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE)) {
    parts.push(text.slice(last, m.index));
    m[1].split(",").map((s) => s.trim()).forEach((id) => {
      const ev = index[id];
      parts.push(
        ev ? <Citation key={`${m.index}-${id}`} evidence={ev} /> : (
          <span key={`${m.index}-${id}`} className="mx-0.5 rounded bg-rose-100 px-1 font-mono text-[10px] text-rose-700" title="Citation not found in sources">
            {id}?
          </span>
        ),
      );
    });
    last = (m.index ?? 0) + m[0].length;
  }
  parts.push(text.slice(last));
  return <>{parts.map((p, i) => <Fragment key={i}>{p}</Fragment>)}</>;
}

export function DraftBody({ text, index = {} }: { text: string; index?: Record<string, Evidence> }) {
  const blocks = text.split(/\n{1,}/).filter((l) => l.trim());
  return (
    <div className="prose-draft text-sm">
      {blocks.map((b, i) => {
        const owner = b.includes("OWNER TO CONFIRM");
        if (b.startsWith("#")) return <h2 key={i}>{b.replace(/^#+\s*/, "")}</h2>;
        if (/^[-*•]\s/.test(b)) return <ul key={i}><li><CitedText text={b.replace(/^[-*•]\s/, "")} index={index} /></li></ul>;
        return (
          <p key={i} className={cn(owner && "rounded bg-amber-50 px-2 dark:bg-amber-500/10")}>
            <CitedText text={b} index={index} />
          </p>
        );
      })}
    </div>
  );
}

export function DraftView({ data, title }: { data: Draft; title: string }) {
  const [copied, setCopied] = useState(false);
  const index: Record<string, Evidence> = {};
  data.statement_check.sentences.forEach((s) => s.evidence.forEach((e) => (index[e.id] = e)));
  data.matrix.forEach((r) => {
    r.evidence?.forEach((e) => (index[e.id] = e));
    if (r.source) index[r.source.id] = r.source;
  });
  const rate = Math.round(data.statement_check.grounding_rate * 100);
  const ungrounded = data.statement_check.sentences.filter((s) => !s.grounded);

  function download() {
    const matrix = data.matrix.map((r) => `| ${r.req_id} | ${r.requirement} | ${r.section} | ${r.gap ? "GAP: " : ""}${r.response} |`).join("\n");
    const md = `# ${title}\n\n${data.statement}\n\n## Compliance Matrix\n\n| Ref | Requirement | Section | Response |\n|---|---|---|---|\n${matrix}\n`;
    const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "bidscout-draft.md" });
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Draft sentences grounded" value={`${rate}%`} good={rate >= 90} />
        <Stat label="Requirements mapped" value={String(data.counts.requirements)} good />
        <Stat label="Gaps for you to fill" value={String(data.counts.gaps)} good={data.counts.gaps === 0} />
      </div>

      {data.review && (
        <div className="rounded-xl ring-1 ring-border">
          <div className="flex items-center gap-2 border-b border-border px-4 py-3 text-sm font-semibold text-fg">
            {data.review.ready_to_submit ? <CheckCircle2 className="size-4 text-emerald-600" /> : <FileWarning className="size-4 text-amber-600" />}
            Final review (Nemotron Ultra)
            {data.review.summary && <span className="font-normal text-fg-muted">: {data.review.summary}</span>}
          </div>
          {data.review.issues?.length > 0 && (
            <ul className="divide-y divide-border">
              {data.review.issues.map((iss, i) => (
                <li key={i} className="flex gap-3 px-4 py-2.5 text-sm">
                  <Badge tone={iss.severity === "high" ? "bad" : iss.severity === "medium" ? "warn" : "neutral"}>{iss.severity}</Badge>
                  <div>
                    <p className="text-fg">{iss.issue}</p>
                    <p className="text-xs text-fg-muted">Fix: {iss.fix}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-fg">Compliance matrix</h3>
          <span className="text-xs text-fg-subtle">Every “shall” and “must” in the RFP, mapped to a response section</span>
        </div>
        <div className="overflow-x-auto rounded-xl ring-1 ring-border">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-fg-subtle">
              <tr>
                <th className="px-3 py-2 font-medium">RFP requirement</th>
                <th className="px-3 py-2 font-medium">Section</th>
                <th className="px-3 py-2 font-medium">How we address it</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.matrix.map((r, i) => (
                <tr key={i} className={cn(r.gap && "bg-amber-50/60 dark:bg-amber-500/5")}>
                  <td className="px-3 py-2.5 align-top text-fg">
                    {r.requirement}
                    {r.source && <Citation evidence={r.source} />}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 align-top text-xs text-fg-muted">{r.section}</td>
                  <td className="px-3 py-2.5 align-top text-fg-muted">
                    <span className="flex items-start gap-1.5">
                      {r.gap ? <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-600" /> : <GroundedMark grounded className="mt-1" />}
                      <span>
                        {r.gap && <b className="text-amber-700 dark:text-amber-400">Gap: </b>}
                        {r.response}
                        <Citations evidence={r.evidence} />
                      </span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-fg">
            <ShieldCheck className="size-4 text-emerald-600" /> Draft capability statement
          </h3>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              className="px-2 py-1 text-xs"
              onClick={() => navigator.clipboard.writeText(data.statement).then(() => setCopied(true))}
            >
              <ClipboardCopy className="size-3.5" /> {copied ? "Copied" : "Copy"}
            </Button>
            <Button variant="ghost" className="px-2 py-1 text-xs" onClick={download}>
              <Download className="size-3.5" /> Export
            </Button>
          </div>
        </div>
        <div className="rounded-xl bg-surface px-5 py-2 ring-1 ring-border">
          <DraftBody text={data.statement} index={index} />
        </div>
        {ungrounded.length > 0 && (
          <details className="mt-3 rounded-lg bg-muted px-3 py-2 text-xs text-fg-muted">
            <summary className="cursor-pointer">{ungrounded.length} sentence{ungrounded.length > 1 ? "s" : ""} without a verified source</summary>
            <ul className="mt-2 list-disc space-y-1 pl-4">
              {ungrounded.map((s, i) => <li key={i}>{s.sentence}</li>)}
            </ul>
          </details>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-xl bg-surface px-4 py-3 ring-1 ring-border">
      <p className="text-xs text-fg-muted">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", good ? "text-fg" : "text-amber-600")}>{value}</p>
    </div>
  );
}
