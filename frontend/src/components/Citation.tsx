"use client";

import { ExternalLink, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { Evidence } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Inline citation chip; hover or focus shows the exact source span it points to. */
export function Citation({ evidence, label }: { evidence: Evidence; label?: string }) {
  const [open, setOpen] = useState(false);
  const host = evidence.url ? new URL(evidence.url).hostname.replace(/^www\./, "") : sourceName(evidence.source);
  return (
    <span className="relative inline-block align-baseline">
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="mx-0.5 rounded bg-brand-soft px-1.5 py-px font-mono text-[10px] font-medium text-brand hover:bg-brand hover:text-white"
      >
        {label ?? evidence.id}
      </button>
      {open && (
        <span className="absolute bottom-full left-1/2 z-50 mb-2 block w-80 -translate-x-1/2 rounded-lg bg-surface p-3 text-left text-xs leading-relaxed text-fg shadow-xl ring-1 ring-border">
          <span className="mb-1.5 flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide text-fg-subtle">
            <span>{host} · {evidence.id}</span>
            {evidence.url && (
              <a href={evidence.url} target="_blank" rel="noreferrer" className="pointer-events-auto text-brand">
                <ExternalLink className="size-3" />
              </a>
            )}
          </span>
          <span className="block">“{evidence.text}”</span>
        </span>
      )}
    </span>
  );
}

function sourceName(source: string) {
  if (source === "notes") return "Owner notes";
  if (source === "profile") return "Company profile";
  if (source === "rfp") return "Solicitation";
  return source;
}

export function Citations({ evidence }: { evidence?: Evidence[] }) {
  if (!evidence?.length) return null;
  return (
    <span>
      {evidence.map((e) => (
        <Citation key={e.id} evidence={e} />
      ))}
    </span>
  );
}

export function GroundedMark({ grounded, className }: { grounded?: boolean; className?: string }) {
  return grounded ? (
    <ShieldCheck className={cn("size-3.5 shrink-0 text-emerald-600", className)} aria-label="Verified against source" />
  ) : (
    <ShieldAlert className={cn("size-3.5 shrink-0 text-amber-600", className)} aria-label="Not verified against source" />
  );
}
