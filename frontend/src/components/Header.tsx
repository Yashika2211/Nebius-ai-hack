"use client";

import { Radar } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import type { Status } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Header() {
  const [status, setStatus] = useState<Status | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    get<Status>("/api/status").then(setStatus).catch(() => setOffline(true));
  }, []);

  const live = status?.llm && status?.search;
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-fg">
          <span className="flex size-7 items-center justify-center rounded-lg bg-brand text-white">
            <Radar className="size-4" />
          </span>
          BidScout
        </Link>
        <nav className="hidden items-center gap-1 text-sm sm:flex">
          <Link href="/" className="rounded-md px-3 py-1.5 text-fg-muted hover:bg-muted hover:text-fg">Companies</Link>
          <Link href="/runs" className="rounded-md px-3 py-1.5 text-fg-muted hover:bg-muted hover:text-fg">Runs &amp; routing</Link>
        </nav>
        <div className="ml-auto flex items-center gap-2 text-xs text-fg-muted">
          <span
            className={cn("size-2 rounded-full", offline ? "bg-rose-500" : live ? "bg-emerald-500" : status ? "bg-amber-500" : "bg-fg-subtle")}
          />
          {offline ? "API offline" : !status ? "Connecting…" : live ? "Live · Nemotron on Token Factory" : "Demo replay mode"}
        </div>
      </div>
    </header>
  );
}
