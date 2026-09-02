// Mirrors docs/API_CONTRACT.md. Keep in sync with services/api/app/schemas.py.

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
