"use client";

import { Award, Briefcase, Building2, ChevronDown, Hash, MapPin, ShieldX } from "lucide-react";
import { useState } from "react";
import type { Profile } from "@/lib/types";
import { Citations, GroundedMark } from "./Citation";
import { Badge, Card } from "./ui";

/** Company profile where every fact carries the source span it was verified against. */
export function ProfileCard({ profile }: { profile: Profile }) {
  const [showDropped, setShowDropped] = useState(false);
  return (
    <Card>
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Building2 className="size-4 text-brand" />
            <h1 className="text-base font-semibold text-fg">{profile.name}</h1>
          </div>
          {profile.demo && <Badge>Demo</Badge>}
        </div>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">{profile.summary}</p>
        {profile.locations?.length > 0 && (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-fg-subtle">
            <MapPin className="size-3" /> {profile.locations.join(" · ")}
          </p>
        )}
      </div>

      <div className="space-y-5 px-5 py-4 text-sm">
        <Section icon={<Hash className="size-3.5" />} title="NAICS codes">
          {profile.naics.map((n) => (
            <Fact key={n.code} grounded={n.grounded} evidence={n.evidence}>
              <span className="font-mono text-xs text-fg">{n.code}</span> {n.title}
            </Fact>
          ))}
        </Section>

        <Section icon={<Award className="size-3.5" />} title="Certifications">
          {profile.certifications.map((c, i) => (
            <Fact key={i} grounded={c.grounded} evidence={c.evidence}>
              <span className="font-medium text-fg">{c.name === "other" ? c.detail : c.name}</span>
              {c.name !== "other" && c.detail && <span className="text-fg-subtle">: {c.detail}</span>}
            </Fact>
          ))}
        </Section>

        <Section icon={<Briefcase className="size-3.5" />} title="Past performance">
          {profile.past_performance.map((p, i) => (
            <Fact key={i} grounded={p.grounded} evidence={p.evidence}>
              <span className="font-medium text-fg">{p.client}</span>: {p.text}
              {p.value && <span className="text-fg-subtle"> · {p.value}</span>}
            </Fact>
          ))}
        </Section>

        <Section title="Capabilities">
          {profile.capabilities.map((c, i) => (
            <Fact key={i} grounded={c.grounded} evidence={c.evidence}>{c.text}</Fact>
          ))}
        </Section>

        {profile.dropped?.length > 0 && (
          <div className="rounded-lg bg-muted px-3 py-2">
            <button
              onClick={() => setShowDropped((s) => !s)}
              className="flex w-full items-center gap-2 text-xs text-fg-muted"
            >
              <ShieldX className="size-3.5 text-amber-600" />
              {profile.dropped.length} unsupported fact{profile.dropped.length === 1 ? "" : "s"} dropped
              <ChevronDown className={`ml-auto size-3.5 transition ${showDropped ? "rotate-180" : ""}`} />
            </button>
            {showDropped && (
              <ul className="mt-2 space-y-1 text-xs text-fg-subtle">
                {profile.dropped.map((d, i) => (
                  <li key={i}>
                    <span className="font-mono">{d.field}</span>: {d.text || d.name || d.code}{" "}
                    {d.quote && <span className="italic">(“{d.quote}” not found in the cited source)</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function Section({ icon, title, children }: { icon?: React.ReactNode; title: string; children: React.ReactNode }) {
  const items = Array.isArray(children) ? children : [children];
  return (
    <div>
      <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {icon} {title}
      </h3>
      {items.length ? <ul className="space-y-1.5">{children}</ul> : <p className="text-xs text-fg-subtle">None found in source</p>}
    </div>
  );
}

function Fact({ grounded, evidence, children }: { grounded?: boolean; evidence?: Profile["spans"]; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-1.5 leading-relaxed text-fg-muted">
      <GroundedMark grounded={grounded} className="mt-1" />
      <span>
        {children}
        <Citations evidence={evidence} />
      </span>
    </li>
  );
}
