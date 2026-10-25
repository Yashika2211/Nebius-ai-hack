export type Tier = "nano" | "super" | "ultra";

export interface Evidence {
  id: string;
  text: string;
  source: string;
  url: string;
}

export interface Grounded {
  citations?: string[];
  quote?: string;
  grounded?: boolean;
  evidence?: Evidence[];
}

export interface Profile {
  id: string;
  name: string;
  website: string;
  summary: string;
  demo?: boolean;
  locations: string[];
  employee_count?: string | null;
  keywords: string[];
  naics: (Grounded & { code: string; title: string })[];
  certifications: (Grounded & { name: string; detail?: string })[];
  capabilities: (Grounded & { text: string })[];
  past_performance: (Grounded & { client: string; text: string; value?: string | null })[];
  clearances: (Grounded & { text: string })[];
  bonding: (Grounded & { text: string })[];
  dropped: (Grounded & { field: string; text?: string; name?: string; code?: string })[];
  spans: Evidence[];
}

export interface FitFactor {
  key: string;
  label: string;
  weight: number;
  score: number;
  grounded: boolean;
  reason: string;
  evidence: Evidence[];
}

export interface Fit {
  score: number;
  band: "strong" | "possible" | "weak";
  factors: FitFactor[];
  headline: string;
  dealbreakers: string[];
}

export interface Opportunity {
  id: string;
  url: string;
  title: string;
  agency?: string | null;
  solicitation_number?: string | null;
  type?: string;
  due_date?: string | null;
  days_left?: number | null;
  set_aside?: string | null;
  naics?: string[];
  place_of_performance?: string | null;
  estimated_value?: string | null;
  summary?: string;
  fit: Fit;
  is_new?: boolean;
  first_seen?: number;
  source_excerpt?: string;
  eligibility?: Eligibility | null;
  draft?: Draft | null;
}

export interface EligibilityItem {
  requirement: Grounded & { id: string; category: string; text: string; mandatory: boolean };
  status: "met" | "not_met" | "unknown";
  dealbreaker: boolean;
  explanation: string;
  action: string;
  profile_evidence: Evidence[];
}

export interface Eligibility {
  verdict: "go" | "caution" | "no_go";
  verdict_reason: string;
  days_left?: number | null;
  items: EligibilityItem[];
  counts: { met: number; not_met: number; unknown: number; dealbreakers: number };
}

export interface MatrixRow extends Grounded {
  req_id: string;
  requirement: string;
  section: string;
  response: string;
  gap: boolean;
  source: Evidence | null;
}

export interface Draft {
  matrix: MatrixRow[];
  statement: string;
  statement_check: {
    sentences: { sentence: string; citations: string[]; grounded: boolean; needs_owner: boolean; evidence: Evidence[] }[];
    grounding_rate: number;
    cited: number;
    total: number;
  };
  review: { issues: { severity: string; issue: string; fix: string }[]; ready_to_submit: boolean; summary: string };
  counts: { requirements: number; gaps: number };
}

export interface TraceEvent {
  seq: number;
  ts: number;
  kind: "llm" | "tool" | "step" | "check" | "note";
  task?: string;
  tier?: Tier;
  model?: string;
  reason?: string;
  tool?: string;
  name?: string;
  detail?: string;
  status?: "ok" | "error";
  cached?: boolean;
  latency_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  cost?: number;
  results?: number;
  error?: string;
}

export interface Savings {
  actual_usd: number;
  ultra_only_usd: number;
  saved_pct: number;
  calls_by_tier: Record<string, number>;
}

export interface RunSummary {
  id: string;
  label: string;
  duration_ms: number;
  llm_calls: number;
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  savings: Savings;
  events?: TraceEvent[];
  started?: number;
}

export interface Status {
  llm: boolean;
  search: boolean;
  demo_mode: string;
  models: Record<Tier, string>;
  routes: Record<string, { tier: Tier; reason: string }>;
  prices: Record<Tier, [number, number]>;
}
