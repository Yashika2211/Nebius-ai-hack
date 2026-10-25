"use client";

import { ArrowRight, Building2, FileCheck2, Globe, Search, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TracePanel } from "@/components/TracePanel";
import { Badge, Button, Card, CardHeader, ErrorNote } from "@/components/ui";
import { get } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { useAgentRun } from "@/lib/useAgentRun";

type ProfileRow = Pick<Profile, "id" | "name" | "website" | "summary" | "demo">;

const STEPS = [
  { icon: Building2, title: "Profile", text: "Reads your site and builds a profile: NAICS, certifications, past performance." },
  { icon: Search, title: "Discover", text: "Searches SAM.gov and state and city portals, then ranks matches with a transparent score." },
  { icon: ShieldCheck, title: "Qualify", text: "Flags dealbreakers like set-asides, bonding, and deadlines, citing the RFP text." },
  { icon: FileCheck2, title: "Draft", text: "Builds a compliance matrix and a first draft, with every claim traceable to a source." },
];

export default function Home() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<ProfileRow[] | null>(null);
  const [website, setWebsite] = useState("");
  const [notes, setNotes] = useState("");
  const [name, setName] = useState("");
  const run = useAgentRun<Profile>();

  useEffect(() => {
    get<ProfileRow[]>("/api/profiles").then(setProfiles).catch(() => setProfiles([]));
  }, []);

  async function onboard(e: React.FormEvent) {
    e.preventDefault();
    const url = website.trim() && !/^https?:\/\//.test(website.trim()) ? `https://${website.trim()}` : website.trim();
    const profile = await run.start("/api/profiles", { website: url, notes, name });
    if (profile) router.push(`/p/${profile.id}`);
  }

  const demo = profiles?.find((p) => p.demo);

  return (
    <div className="space-y-10">
      <section className="grid gap-8 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div>
          <Badge tone="info"><Sparkles className="size-3" /> NVIDIA Nemotron on Nebius Token Factory</Badge>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-fg sm:text-4xl">
            Win government contracts without a proposal team.
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-fg-muted">
            Small businesses miss set-aside contracts because finding the right RFP, checking eligibility, and
            drafting a compliant response takes days. BidScout does it in minutes and cites a source for every claim.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {demo && (
              <Link href={`/p/${demo.id}`}>
                <Button>Try the demo company <ArrowRight className="size-4" /></Button>
              </Link>
            )}
            <a href="#onboard"><Button variant="secondary">Add your company</Button></a>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <Card key={title} className="p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-fg">
                <span className="flex size-6 items-center justify-center rounded-md bg-brand-soft text-xs text-brand">{i + 1}</span>
                <Icon className="size-4 text-fg-subtle" /> {title}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">{text}</p>
            </Card>
          ))}
        </div>
      </section>

      {profiles && profiles.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-fg">Your companies</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {profiles.map((p) => (
              <Link key={p.id} href={`/p/${p.id}`}>
                <Card className="h-full p-4 transition hover:ring-brand">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-fg">{p.name}</span>
                    {p.demo && <Badge>Demo</Badge>}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-fg-muted">{p.summary}</p>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section id="onboard" className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader
            icon={<Globe className="size-4" />}
            title="Onboard a company"
            subtitle="We crawl your website with Tavily and Nemotron Super pulls out a profile. Any fact we can't trace back to your site or notes gets dropped."
          />
          <form onSubmit={onboard} className="space-y-4 p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-fg">Company website</span>
                <input
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="acme-facilities.com"
                  className="mt-1 w-full rounded-lg bg-surface px-3 py-2 text-sm ring-1 ring-border placeholder:text-fg-subtle focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-fg">Company name <span className="font-normal text-fg-subtle">(optional)</span></span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Acme Facilities LLC"
                  className="mt-1 w-full rounded-lg bg-surface px-3 py-2 text-sm ring-1 ring-border placeholder:text-fg-subtle focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </label>
            </div>
            <label className="block">
              <span className="text-sm font-medium text-fg">Capabilities, certifications, past work</span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={5}
                placeholder="We're a WOSB-certified janitorial company in Austin, TX (NAICS 561720). We clean 3 county clinics under a $400K contract…"
                className="mt-1 w-full rounded-lg bg-surface px-3 py-2 text-sm ring-1 ring-border placeholder:text-fg-subtle focus:outline-none focus:ring-2 focus:ring-brand"
              />
            </label>
            {run.error && <ErrorNote message={run.error} />}
            <div className="flex items-center justify-between gap-4">
              <p className="text-xs text-fg-subtle">Takes about 30–60 seconds. Watch every step in the trace.</p>
              <Button type="submit" loading={run.running} disabled={!website.trim() && !notes.trim()}>
                Build profile
              </Button>
            </div>
          </form>
        </Card>
        <TracePanel events={run.events} summary={run.summary} running={run.running} className="h-[420px]" />
      </section>
    </div>
  );
}
