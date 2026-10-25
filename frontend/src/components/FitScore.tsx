import type { Fit } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Citations, GroundedMark } from "./Citation";

const BAND = {
  strong: { ring: "stroke-emerald-500", text: "text-emerald-600", label: "Strong fit" },
  possible: { ring: "stroke-amber-500", text: "text-amber-600", label: "Possible fit" },
  weak: { ring: "stroke-rose-500", text: "text-rose-600", label: "Weak fit" },
};

export function FitRing({ score, band, size = 56 }: { score: number; band: Fit["band"]; size?: number }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const style = BAND[band] ?? BAND.weak;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} aria-label={`Fit score ${score} of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={6} className="stroke-muted" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - score / 100)}
          className={cn(style.ring, "transition-all duration-700")}
        />
      </svg>
      <span className={cn("absolute inset-0 flex items-center justify-center text-sm font-bold tabular-nums", style.text)}>
        {score}
      </span>
    </div>
  );
}

export function bandLabel(band: Fit["band"]) {
  return (BAND[band] ?? BAND.weak).label;
}

/** Factor-by-factor breakdown: weight, score, the model's reason, and its source evidence. */
export function FitBreakdown({ fit }: { fit: Fit }) {
  return (
    <div className="divide-y divide-border">
      {fit.factors.map((f) => (
        <div key={f.key} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 py-3">
          <div className="flex items-center gap-1.5 text-sm font-medium text-fg">
            {f.label}
            <span className="text-xs font-normal text-fg-subtle">· {Math.round(f.weight * 100)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full", f.score >= 7 ? "bg-emerald-500" : f.score >= 4 ? "bg-amber-500" : "bg-rose-500")}
                style={{ width: `${f.score * 10}%` }}
              />
            </div>
            <span className="w-8 text-right text-xs tabular-nums text-fg-muted">{f.score}/10</span>
          </div>
          <p className="col-span-2 flex items-start gap-1.5 text-sm leading-relaxed text-fg-muted">
            <GroundedMark grounded={f.grounded} className="mt-1" />
            <span>
              {f.reason}
              <Citations evidence={f.evidence} />
              {!f.grounded && <span className="ml-1 text-xs text-amber-700 dark:text-amber-400">(unverified, counted at half weight)</span>}
            </span>
          </p>
        </div>
      ))}
    </div>
  );
}
