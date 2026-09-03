// Mirrors docs/API_CONTRACT.md. Keep in sync with services/api/app/schemas.py (data plane)
// and xano/ (control plane: auth, alert prefs, in-app inbox, plan).

export type Severity = "low" | "medium" | "high";
export type ChangeKind =
  | "creative_launched"
  | "creative_dropped"
  | "creative_surge"
  | "new_serp_advertiser"
  | "serp_advertiser_left"
  | "serp_position_shift"
  | "trend_spike"
  | "trend_decline"
  | "rising_query";

export interface WatchlistSummary {
  id: number;
  name: string;
  vertical: string;
  geo: string;
  location?: string | null;
  competitor_count: number;
  keyword_count: number;
  last_run_at: string | null;
  open_changes: number;
}

export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "done" | "failed";
  searches_used: number;
  error?: string | null;
}

export interface Competitor {
  id: number;
  name: string;
  domain: string;
  advertiser_id: string | null;
  active_creatives: number;
}

export interface Keyword {
  id: number;
  term: string;
}

export interface WatchlistDetail {
  id: number;
  name: string;
  vertical: string;
  geo: string;
  location?: string | null;
  created_at: string;
  competitors: Competitor[];
  keywords: Keyword[];
  last_run: Run | null;
}

export interface Change {
  id: number;
  run_id: number;
  kind: ChangeKind;
  severity: Severity;
  subject_type: "competitor" | "keyword";
  subject_id: number;
  subject_label: string;
  detected_at: string;
  insight_id: number | null;
  payload: Record<string, unknown>;
}

export interface Action {
  action: string;
  rationale: string;
  effort: "low" | "medium" | "high" | string;
  urgency: "now" | "this_week" | "monitor" | string;
}

export interface Insight {
  id: number;
  run_id: number;
  created_at: string;
  model: string;
  confidence: number;
  summary: string;
  why_it_matters: string;
  recommended_actions: Action[];
  change_ids: number[];
  changes: Change[];
}

export interface Creative {
  id: number;
  competitor_id: number;
  creative_id: string;
  format: "text" | "image" | "video";
  platform: string | null;
  target_domain: string | null;
  image_url: string | null;
  details_url: string | null;
  first_shown: string | null;
  last_shown: string | null;
  active: boolean;
  first_seen_run_id: number;
  last_seen_run_id: number;
  text: { headline?: string; description?: string; title?: string } | null;
  /** Days actually served, distinct from the first_shown -> last_shown span. */
  total_days_shown?: number | null;
}

export interface SerpAd {
  position: number;
  block: "top" | "bottom";
  advertiser_domain: string;
  title: string;
  description: string | null;
  displayed_link: string | null;
  is_tracked_competitor: boolean;
  competitor_id: number | null;
}

export interface SerpOut {
  keyword: Keyword;
  run_id: number | null;
  ads: SerpAd[];
  share_of_voice: { advertiser_domain: string; appearances: number; avg_position: number }[];
}

export interface TrendsOut {
  keyword: Keyword;
  run_id: number | null;
  timeline: { date: string; value: number }[];
  related_rising: { query: string; value_text: string; value_num: number | null }[];
  related_top: { query: string; value_text: string; value_num: number | null }[];
}

export interface CollectAnalyzeOut {
  run: Run;
  snapshots: number;
  changes: Change[];
  insights: Insight[];
  alerts_sent: number;
}

// ---- usage & budget (data plane GET /usage) ----------------------------------------------------

export type PlanKey = "free" | "team" | "agency";

export interface PlanCadence {
  creatives_per_day: number;
  serp_per_day: number;
  trends_per_day: number;
  related_per_week: number;
}

export interface PlanInfo {
  key: PlanKey;
  name: string;
  price_usd: number;
  watchlists: number;
  competitors_per_watchlist: number;
  keywords_per_watchlist: number;
  searches_per_month: number;
  cadence: PlanCadence;
  blurb: string;
}

export interface WatchlistUsage {
  watchlist_id: number;
  name: string;
  competitors: number;
  keywords: number;
  searches_used: number;
  runs: number;
  last_run_at: string | null;
  searches_per_run: number;
  projected_month_current: number;
  projected_month_plan: number;
  over_plan_limits: boolean;
  llm_cost_usd: number;
}

export interface LlmFeatureCost { feature: string; calls: number; cost_usd: number }
export interface LlmModelCost { model: string; calls: number; cost_usd: number }

/** Claude spend for the period. `unpriced_calls` counts calls whose model has no
 *  published rate — tokens are recorded but cost is 0, so the total understates. */
export interface LlmUsage {
  calls: number;
  cost_usd: number;
  unpriced_calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  by_feature: LlmFeatureCost[];
  by_model: LlmModelCost[];
  metering_since: string | null;
}

export interface UsageOut {
  workspace_id: number;
  plan: PlanKey;
  period_start: string;
  period_end: string;
  searches_used: number;
  searches_budget: number;
  searches_remaining: number;
  budget_used_pct: number;
  runs: number;
  cost_to_date_usd: number;
  projected_month_current_cadence: number;
  projected_month_plan_cadence: number;
  projected_cost_current_usd: number;
  projected_cost_plan_usd: number;
  rate_per_search_usd: number;
  watchlists_used: number;
  watchlists_limit: number;
  by_watchlist: WatchlistUsage[];
  plans: PlanInfo[];
  llm: LlmUsage;
  /** SerpApi searches + Claude tokens */
  total_cost_usd: number;
}

// ---- control plane (Xano) ---------------------------------------------------------------------

export type AlertChannel = "in_app" | "webhook" | "email";
export type AlertProvider = "in_app" | "slack" | "discord" | "teams" | "generic" | "email";

export interface XanoMe {
  id: number;
  name: string;
  email: string;
  workspace_id: number;
  role: "owner" | "member" | "viewer";
  workspace: { id: number; name: string; plan: PlanKey };
}

export interface AlertPref {
  id: number;
  created_at: number | string;
  workspace_id: number;
  channel: AlertChannel;
  provider: AlertProvider | string | null;
  label: string | null;
  target: string | null;
  min_severity: Severity;
  enabled: boolean;
}

export interface XanoAlert {
  id: number;
  created_at: number | string;
  workspace_id: number;
  alert_pref_id: number | null;
  insight_id: number | null;
  watchlist_id: number | null;
  channel: AlertChannel;
  severity: Severity;
  title: string | null;
  summary: string | null;
  why_it_matters: string | null;
  dashboard_url: string | null;
  read: boolean;
  status: "sent" | "failed" | "skipped";
  detail: string | null;
}

export interface XanoAlertsOut {
  unread: number;
  alerts: XanoAlert[];
}

export interface AlertDelivery {
  channel: string;
  status: "pending" | "sent" | "failed";
  target: string;   // redacted server-side; never the full webhook URL
  sent_at: string | null;
  error: string | null;
}

/** GET /alerts — the workspace-wide feed. `id` is the insight id. */
export interface AlertFeedItem {
  id: number;
  watchlist_id: number;
  watchlist_name: string;
  severity: Severity;
  summary: string;
  why_it_matters: string;
  created_at: string;
  delivery: AlertDelivery | null;
}

export type ProviderStatus = "ok" | "invalid" | "exhausted" | "unset" | "unreachable";

/** GET /providers/serpapi — validity and quota, not mere key presence. */
export interface SerpApiStatus {
  status: ProviderStatus;
  key_source: "workspace" | "platform" | "none";
  plan: string | null;
  /** total spendable = plan_searches_left + extra_credits */
  searches_left: number | null;
  plan_searches_left: number | null;
  extra_credits: number | null;
  searches_per_month: number | null;
  used_this_month: number | null;
  cached: boolean;
}

export type ProviderKind = "serpapi" | "anthropic";

/** GET /workspace/keys — never carries key material, only the last four characters. */
export interface WorkspaceKey {
  kind: ProviderKind;
  last4: string;
  created_at: string;
  updated_at: string;
}

export interface TrendsCategory { id: number; name: string }

export interface ProposedCompetitor { domain: string; name: string; reason: string }

export interface CompanyAssetIn { kind: "brand" | "property" | "catalogue"; key: string; value: string }

/** POST /onboarding/analyze — a proposal. Nothing is persisted until /create. */
export interface OnboardingProposal {
  vertical: TrendsCategory | null;
  keywords: string[];
  competitors: ProposedCompetitor[];
  assets: CompanyAssetIn[];
  /** vocabulary that marks a search as being in this market; stops a keyword scan drifting */
  market_terms: string[];
  /** false when the site could not be fetched; the answer came from the description alone */
  site_read: boolean;
}

export interface OnboardingResult {
  watchlist_id: number;
  competitors: { domain: string; verified: boolean }[];
  /** domains the user kept that were not persisted, and why */
  skipped: { domain: string; reason: string }[];
  searches_used: number;
}
