# BidScout: Devpost submission

**Tagline:** An AI agent that finds, qualifies, and drafts government contract bids for small businesses, with a source cited for every claim.

**Track:** Best Apps and Agents

---

## Inspiration

The US government reserves a share of its contracting dollars for small businesses: women-owned,
veteran-owned, HUBZone, and 8(a) firms. The money is there, but the process isn't built for a company
without a proposal team. Opportunities are scattered across SAM.gov and dozens of state and city portals.
Each solicitation is a 40–120 page PDF full of set-aside rules, size standards, bonding and insurance
minimums, and "shall" statements. Deciding whether one is worth pursuing can take a day, and a compliant
response takes a week. So most eligible businesses never bid, and large primes with full-time capture teams
win by default.

We wanted to give a 40-person janitorial company the equivalent of a capture manager and a proposal writer.

## What it does

BidScout takes a small business from "who are you?" to a first-draft bid in minutes:

1. **Onboard:** paste your website. BidScout crawls it and builds a profile (NAICS codes, certifications,
   past performance), and every fact links to the sentence it came from. Facts it can't verify get dropped,
   and you can see which ones.
2. **Discover:** it searches SAM.gov and state and city procurement portals, triages every result, reads the
   best solicitations in full, and ranks them with a **transparent fit score**: six factors, fixed weights,
   each with a cited reason.
3. **Qualify:** it extracts disqualifying requirements (set-asides, bonding, clearances, insurance, deadlines)
   and tells you go, caution, or no-go, with the exact RFP language and the next step for each unknown.
4. **Draft:** it builds a **compliance matrix** (every "shall" mapped to a response section, gaps flagged)
   and streams a first-draft capability statement where every sentence cites the RFP or your profile. Then
   Nemotron Ultra reviews it.
5. **Watch:** it re-scans daily and surfaces only new matches.

A live **agent trace** shows every model call: which Nemotron model ran it, why, latency, tokens, and cost.
It also shows the measured savings from routing against running everything on the largest model.

## How we built it

- **Nebius Token Factory + NVIDIA Nemotron:** all inference runs on Token Factory's OpenAI-compatible API.
  A router sends each task to the cheapest Nemotron tier that handles it well:
  - **Nano** for high-volume work: search query planning, batched relevance triage, solicitation field
    extraction.
  - **Super** for long-context extraction and writing: company profiles, requirement extraction,
    compliance matrices, drafts.
  - **Ultra** for decisions that matter: fit scoring, eligibility and dealbreaker reasoning, final compliance
    review.
  Low-confidence Nano triage escalates to a bigger tier automatically. Model IDs are resolved at startup from
  `/v1/models`.
- **Measured, not estimated:** every call records real token usage, and the trace computes actual cost vs.
  the same tokens on Ultra. An eval harness runs the pipeline in a forced Ultra-only mode on hand-labeled
  real solicitations to compare accuracy as well as cost.
- **Grounding:** sources are split into numbered spans. Models must cite span IDs plus a verbatim quote, and a
  verifier rejects citations that don't exist or whose quote isn't in the span. Unverified profile facts are
  dropped, unverified "met" decisions become "unknown", and unverified fit reasons count at half weight.
- **Tavily:** **crawl** (with natural-language instructions) for onboarding across a company's whole site,
  **search** restricted to 13 procurement domains for discovery, and **extract** for full solicitation text,
  so eligibility and the compliance matrix are grounded in the actual RFP.
- **Stack:** FastAPI backend streaming trace events and tokens over Server-Sent Events, a Next.js + Tailwind
  frontend, SQLite, Docker on Render's free tier, Vercel, and a GitHub Actions cron for the daily watch job.
- **Reliability:** every model and search response is cached. If a live call fails during a demo, the cached
  response is served and labeled as such in the trace.

## Challenges we ran into

- **Hallucinated eligibility is worse than no answer.** Telling a business it qualifies for an 8(a) set-aside
  when it doesn't wastes a week of their time. Prompting alone didn't fix it. We built the span-and-quote
  verifier, and moved the most common dealbreakers (set-aside certification match, expired deadlines) into
  deterministic code.
- **Search results are mostly not solicitations.** Award notices, news, and vendor ads dominate. Batched Nano
  triage with confidence-based escalation filtered them cheaply without dropping real opportunities.
- **Making a score explainable.** A single model-generated "fit: 82" isn't actionable. We split it into six
  scored factors with fixed weights in code, so the same evidence always gives the same score.

## Accomplishments that we're proud of

- An end-to-end agent a real small business owner could use today, from website to first draft.
- Every claim in the product links to its source sentence. Hover any citation to see it.
- Visible, measured multi-model routing on Nemotron, with an eval harness comparing quality and cost against
  an Ultra-only baseline.

## What we learned

- Routing works best when tasks are split finely. "Draft a proposal" is one Ultra call, but "triage, extract,
  score, decide, draft, review" is six calls, and most of them don't need the biggest model.
- Grounding has to be enforced in code. Asking the model to cite isn't enough: you have to check the quote.
- Government procurement is a domain where "probably right" isn't useful, so conservative "unknown, here's what
  to confirm" answers build more trust than confident guesses.

## What's next for BidScout

- Parse attached solicitation PDFs and amendments, not just the listing page.
- SAM.gov entity registration lookup (UEI, CAGE, SBA certifications) to verify the profile automatically.
- Teaming: match businesses that miss a requirement with certified primes or subcontractors.
- Email and Slack alerts from watch mode, and run the watch job on Nebius Serverless Jobs.

---

## Feedback on Nebius Token Factory and NVIDIA Nemotron

_(For the Most Valuable Feedback prize. Specific, reproducible, and written from building BidScout.)_

**What worked well**
- The OpenAI-compatible API meant zero new SDK code. We pointed the official `openai` client at the base URL
  and everything (chat, JSON mode, streaming with usage) worked as expected.
- Having Nano, Super and Ultra from one model family behind one API made per-task routing practical. Prompts
  carried across tiers with no changes.

**Friction we hit**
1. **No public model ID table.** The quickstart shows a single example model, and the Nemotron IDs aren't on a
   public page. Third-party listings disagree on casing (`nvidia/nemotron-3-super-120b-a12b` vs
   `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`), which matters because IDs are case-sensitive. *Suggestion:* a
   public, copyable table with exact ID, context length, price, and supported features (JSON mode, tools,
   reasoning toggle) per model.
2. **The pricing page needs a login.** `nebius.com/token-factory/prices` redirects to the authenticated console,
   so you can't estimate cost before signing up. *Suggestion:* a public pricing page, and per-model prices in
   the `/v1/models` response so apps can compute cost without hardcoding.

_More items will be added from live usage before submission._
