import { CircleCheck, CircleHelp, CircleX, OctagonAlert } from "lucide-react";
import type { Eligibility } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Citations } from "./Citation";
import { Badge } from "./ui";

const VERDICT = {
  go: { label: "Go: you appear eligible", tone: "bg-emerald-50 text-emerald-900 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-200 dark:ring-emerald-500/30", Icon: CircleCheck },
  caution: { label: "Caution: confirm a few items first", tone: "bg-amber-50 text-amber-900 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-200 dark:ring-amber-500/30", Icon: CircleHelp },
  no_go: { label: "No-go: dealbreaker found", tone: "bg-rose-50 text-rose-900 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-200 dark:ring-rose-500/30", Icon: OctagonAlert },
};

const STATUS = {
  met: { Icon: CircleCheck, cls: "text-emerald-600", label: "Met" },
  not_met: { Icon: CircleX, cls: "text-rose-600", label: "Not met" },
  unknown: { Icon: CircleHelp, cls: "text-amber-600", label: "Unknown" },
};

export function EligibilityView({ data }: { data: Eligibility }) {
  const v = VERDICT[data.verdict] ?? VERDICT.caution;
  const items = [...data.items].sort((a, b) => Number(b.dealbreaker) - Number(a.dealbreaker) || order(a.status) - order(b.status));
  return (
    <div className="space-y-4">
      <div className={cn("flex items-start gap-3 rounded-xl px-4 py-3 ring-1", v.tone)}>
        <v.Icon className="mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-semibold">{v.label}</p>
          {data.verdict_reason && <p className="mt-0.5 text-sm opacity-90">{data.verdict_reason}</p>}
          <p className="mt-1 text-xs opacity-75">
            {data.counts.met} met · {data.counts.unknown} to confirm · {data.counts.not_met} not met
          </p>
        </div>
      </div>

      <ul className="divide-y divide-border rounded-xl ring-1 ring-border">
        {items.map((item) => {
          const s = STATUS[item.status] ?? STATUS.unknown;
          return (
            <li key={item.requirement.id} className="space-y-1.5 px-4 py-3">
              <div className="flex items-start gap-2">
                <s.Icon className={cn("mt-0.5 size-4 shrink-0", s.cls)} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-fg">{item.requirement.text}</span>
                    {item.dealbreaker && <Badge tone="bad">Dealbreaker</Badge>}
                    {item.requirement.mandatory && !item.dealbreaker && <Badge>Mandatory</Badge>}
                    <Badge className="font-mono">{item.requirement.category}</Badge>
                  </div>
                  {item.requirement.quote && (
                    <p className="mt-1 text-xs italic text-fg-subtle">
                      RFP: “{item.requirement.quote}”
                      <Citations evidence={item.requirement.evidence} />
                    </p>
                  )}
                  <p className="mt-1 text-sm text-fg-muted">
                    {item.explanation}
                    <Citations evidence={item.profile_evidence} />
                  </p>
                  {item.action && item.status !== "met" && (
                    <p className="mt-1 text-xs font-medium text-brand">Next step: {item.action}</p>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function order(s: string) {
  return s === "not_met" ? 0 : s === "unknown" ? 1 : 2;
}
