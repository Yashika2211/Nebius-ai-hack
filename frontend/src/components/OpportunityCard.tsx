import { Building, CalendarClock, ChevronRight, Tag } from "lucide-react";
import Link from "next/link";
import type { Opportunity } from "@/lib/types";
import { dueLabel } from "@/lib/utils";
import { bandLabel, FitRing } from "./FitScore";
import { Badge, Card } from "./ui";

export function OpportunityCard({ opp, profileId }: { opp: Opportunity; profileId: string }) {
  const closed = opp.days_left !== null && opp.days_left !== undefined && opp.days_left < 0;
  const urgent = !closed && opp.days_left !== null && opp.days_left !== undefined && opp.days_left < 10;
  return (
    <Link href={`/p/${profileId}/o/${opp.id}`} className="group block">
      <Card className="flex items-start gap-4 p-4 transition group-hover:ring-brand">
        <FitRing score={opp.fit?.score ?? 0} band={opp.fit?.band ?? "weak"} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <h3 className="line-clamp-2 font-medium leading-snug text-fg">{opp.title}</h3>
            <ChevronRight className="mt-0.5 size-4 shrink-0 text-fg-subtle transition group-hover:translate-x-0.5 group-hover:text-brand" />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-muted">
            {opp.agency && (
              <span className="flex items-center gap-1"><Building className="size-3" /> {opp.agency}</span>
            )}
            <span className={`flex items-center gap-1 ${closed ? "text-rose-600" : urgent ? "text-amber-700" : ""}`}>
              <CalendarClock className="size-3" /> {dueLabel(opp.days_left, opp.due_date)}
            </span>
            {opp.set_aside && (
              <span className="flex items-center gap-1"><Tag className="size-3" /> {opp.set_aside}</span>
            )}
          </div>
          {opp.fit?.headline && <p className="mt-2 line-clamp-2 text-sm text-fg-muted">{opp.fit.headline}</p>}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge tone={opp.fit?.band === "strong" ? "good" : opp.fit?.band === "possible" ? "warn" : "bad"}>
              {bandLabel(opp.fit?.band ?? "weak")}
            </Badge>
            {opp.is_new && <Badge tone="info">New</Badge>}
            {opp.type && <Badge>{opp.type}</Badge>}
            {opp.fit?.dealbreakers?.length > 0 && <Badge tone="bad">{opp.fit.dealbreakers.length} possible dealbreaker{opp.fit.dealbreakers.length > 1 ? "s" : ""}</Badge>}
          </div>
        </div>
      </Card>
    </Link>
  );
}
