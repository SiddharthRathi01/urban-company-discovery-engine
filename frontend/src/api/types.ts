// Shapes of the backend responses that the screens use (see docs/BACKEND.md).
export type SentimentName = "Positive" | "Neutral" | "Negative" | "Mixed" | "Uncertain" | "Unclear";
export type SentimentBlock = Record<SentimentName, { n: number; pct: number }>;
export interface SourceCount { source: string; n: number; pct: number }

export interface Overview {
  product: string;
  business_metric: string;
  dataset: {
    reviews_analysed: number;
    date_range: { earliest: string; latest: string };
    by_source: SourceCount[];
    sentiment: SentimentBlock;
    rating: { rated_reviews: number; mean: number; pct_1_2_star: number; distribution: Record<string, number> };
    service_category_stated: number;
    city_stated: number;
  };
  headline_metrics: { reviews_with_at_least_one_theme: number };
  method: { summary: string; validation: string };
}

export interface Subtheme { subtheme_id: string; name: string; n: number; pct_of_dataset: number; pct_of_theme: number; negative_or_mixed_share: number; rule_precision_estimate: number | null }
export interface Theme {
  theme_id: string;
  name: string;
  definition: string;
  review_count: number;
  pct_of_dataset: number;
  sentiment: SentimentBlock;
  by_source: { source: string; n: number; pct_of_source_reviews: number }[];
  subthemes: Subtheme[];
  return_signals: { return: number; non_return: number; non_return_pct: number; return_stated_or_signalled: number; non_return_stated_or_signalled: number; non_return_stated_or_signalled_pct: number };
  evidence_score: { score: number };
  evidence_rank: number;
  interpretation: string;
  representative_evidence_ids: string[];
}

export interface Evidence {
  evidence_id: string;
  review_id: string;
  original_review_id: string;
  quote: string;
  source: string;
  source_url: string;
  review_date: string | null;
  rating: string | null;
  sentiment_label: SentimentName;
  service_category: string | null;
  city: string | null;
  review_text?: string;
  supports: string[];
}

export interface PmBrief {
  problem: string;
  who_is_affected: string;
  why_it_happens_hypotheses: string[];
  proposal: { title: string; what: string }[];
  why_it_should_lift_repeat_booking: string;
  success_looks_like: string;
  watch_outs: string;
  effort: "S" | "M" | "L";
  effort_note: string;
  evidence_confidence: "High" | "Medium" | "Low";
  recommendation: "Start now" | "Quick win" | "Plan next" | "Validate first";
  labels: string;
}
export interface Opportunity {
  opportunity_id: string;
  title: string;
  customer_problem: string;
  supporting_segment: string | null;
  top_service_categories_in_evidence: Record<string, number>;
  evidence: {
    reviews: number;
    pct_of_dataset: number;
    by_source: Record<string, number>;
    sentiment: SentimentBlock;
    negative_share_pct: number;
    non_return_pct: number;
    return_pct: number;
    switching_or_warning_or_non_return_pct: number;
    baseline_switching_or_warning_or_non_return_pct: number;
    related_theme: string;
    related_unmet_needs: string[];
  };
  expected_customer_benefit: string;
  influence_on_repeat_booking_hypothesis: string;
  suggested_improvement_hypothesis: string;
  suggested_success_metric: string;
  pm_brief: PmBrief;
  prioritisation: { frequency: number; severity: number; evidence_strength: number; repeat_relevance: number; impact_judgement_1_to_5: number; score: number; formula: string };
  priority_rank: number;
  priority: "High" | "Medium" | "Low";
  priority_rationale: string;
  evidence_quotes?: Evidence[];
}

export interface BehaviourClass { class: string; n: number; pct_of_dataset: number; by_basis: Record<string, number> }
export interface BehaviourSummary {
  classified: number; classified_pct: number; target_pct: number; target_met: boolean;
  return: number; return_pct: number; non_return: number; non_return_pct: number; insufficient: number; insufficient_pct: number;
  by_basis: Record<"Stated" | "Signalled" | "Inferred", { n: number; pct_of_dataset: number }>;
  by_confidence_of_classified: Record<"High" | "Medium" | "Low", { n: number; pct_of_classified: number }>;
}
export interface SegmentSplit { segment: string; n: number; return_pct: number; non_return_pct: number; insufficient_pct: number; return_pct_of_classified: number }
export type CompareGroup = "all" | "return" | "non_return" | "return_stated_signalled" | "non_return_stated_signalled";
export interface Behaviour {
  summary: BehaviourSummary;
  definitions: Record<string, string>;
  basis_definitions: Record<string, string>;
  caution: string;
  distribution: BehaviourClass[];
  patterns: string[];
  stated_returners_dissatisfied: { n: number; of: number; pct: number };
  classes: Record<string, { signalled_reasons?: Record<string, { n: number; pct_of_dataset: number; evidence_ids: string[] }>; reasons: Record<string, number> }>;
  comparison: {
    groups: Record<CompareGroup, number>;
    theme_prevalence_pct: Record<string, Record<CompareGroup, number>>;
    prevalence_pct: Record<string, { label: string } & Record<CompareGroup, number>>;
    top_leaving_drivers: { issue: string; code: string; non_return_pct: number; return_pct: number; gap_points: number }[];
    top_staying_drivers: { issue: string; code: string; return_pct: number; non_return_pct: number; gap_points: number }[];
    return_share_by_segment: { service_category: SegmentSplit[]; source: SegmentSplit[]; city: SegmentSplit[] };
    caution: string;
  };
}
export interface BehaviourDetail {
  class: string;
  n: number;
  by_basis: Record<string, number>;
  stated_records?: { review_id: string; source: string; source_url: string; reason: string; evidence_id: string }[];
  representative_evidence_ids?: string[];
  at_risk_loyal_customers_evidence_ids?: string[];
  signalled_reasons?: Record<string, { n: number; pct_of_dataset: number; evidence_ids: string[] }>;
  inferred_evidence_ids?: string[];
  evidence_quotes: Evidence[];
}

export interface Alternative {
  alternative_id: string;
  alternative_type: string;
  relevant_mentions: number;
  by_tier: { reported_use: number; considering: number; general_or_hypothetical: number };
  used_for: string;
  why_customers_choose_it: string[];
  customer_reported_advantages: string[];
  customer_reported_disadvantages: string[];
}

export interface NeedItem {
  unmet_need_id: string;
  name: string;
  definition: string;
  n_reviews: number;
  pct_of_dataset: number;
  linked_opportunity: string;
  rank_by_frequency: number;
  rule_precision_estimate: number;
  return_relevance: { non_return_pct: number; non_return_stated_or_signalled: number; stated_return_but_negative: number; switching_or_warning_signals_pct: number; baseline_switching_or_warning_signals_pct: number };
}

export interface Segment {
  segment_id: string;
  name: string;
  n?: number;
  n_vetted_examples?: number;
  small_sample: boolean;
  sentiment_pct?: Record<string, number>;
  theme_prevalence: Record<string, { n: number; pct: number }>;
  dominant_themes: string[];
  important_difference?: string;
  evidence_quotes?: Evidence[];
}

export interface Question { question_id: string; question: string; summary: string; evidence_strength: string; gaps: string[]; evidence_quotes?: Evidence[] }

export interface MoodRow { key: string; label: string; n: number; positive: number; neutral: number; negative: number; mixed: number; uncertain: number; negative_share: number; positive_share: number }

export interface ReviewRow {
  record_id: string;
  original_review_id: string;
  source: string;
  source_url: string;
  review_date: string | null;
  rating: string | null;
  sentiment_label: SentimentName;
  service_category: string | null;
  city: string | null;
  review_title: string | null;
  review_text: string;
  review_text_truncated?: boolean;
  themes: string[];
  return_class: string;
  return_basis: string;
  return_confidence: string;
  return_reason: string;
  issues: string[];
  unmet_needs: string[];
  alternatives: string[];
  opportunities?: { opportunity_id: string; title: string; priority: string; priority_rank: number }[];
  evidence?: Evidence[];
}

export interface AskResult {
  query: string;
  search_words: string[];
  matched_question: { question_id: string; question: string; summary: string; evidence_strength: string } | null;
  comments: { record_id: string; source: string; source_url: string; review_date: string | null; rating: string | null; sentiment_label: SentimentName; themes: string[]; excerpt: string; matched_words: string[] }[];
  total_matching_reviews: number;
  mode: string;
  note: string;
}

export interface Trust {
  sources: { source: string; kind: string; reviews: number; how: string; what_it_adds: string; sentiment_pct: Record<string, number> }[];
  funnel: { step: string; n: number; note: string }[];
  pipeline: { id: string; title: string; what: string; numbers: string; where: string }[];
  bias: Record<"negative_voice" | "silent_churn", { title: string; facts: string[]; what_we_did: string[]; equal_weight?: { pooled: Record<string, number>; equal_weight_across_4_sources: Record<string, number> }; gap?: string }>;
  validation: {
    sentiment: { sample: number; agreed: number; agreement_pct: number; queue_read_individually: number; labels_changed_by_analyst: number; note: string };
    quotes: { verified: number; total: number; note: string };
    urls: { individually_verified: number; reddit_permalinks_unverified: number; missing: number; note: string };
    rule_precision: { issue: string; code: string; precision_pct: number }[];
    rule_precision_note: string;
    tests: { automated_tests: number; covers: string };
  };
  golden_set: { status: string; title: string; note: string };
  limitations: Record<string, string>;
  tiles: { value: string; label: string }[];
}

export interface Limitations { dataset_characteristics: Record<string, Record<string, unknown>>; method_limitations: Record<string, string>; interpretation_guidance: string[] }

export interface UploadMeta {
  upload_id: string;
  filename: string;
  size_bytes: number;
  status: string;
  analysis_status: string;
  summary: { rows_in_file: number; accepted: number; rejected: number; malformed: number; duplicates_in_file: number; already_in_approved_dataset: number; rows_with_warnings: number };
}
export interface UploadValidation { issues: { line: number; severity: string; code: string; message: string }[]; column_mapping: Record<string, string>; issue_counts: Record<string, number> }
export interface UploadJob { job_id: string | null; status: string; message: string; provider?: string }

export interface NeedDetail extends NeedItem { evidence_quotes?: Evidence[] }

// ---- LLM (Cloudflare Workers AI) ----
export interface LlmStatus { provider: string; model: string; configured: boolean; thinking_enabled: boolean; daily_neuron_budget: number; usage_today_neurons: number }
export interface LlmUsage {
  requests: number; successful_requests: number; failed_requests: number; input_tokens: number; output_tokens: number; neurons: number; seconds: number;
  neurons_today: number; daily_neuron_budget: number; by_purpose: Record<string, { requests: number; failed: number; input_tokens: number; output_tokens: number; neurons: number; seconds: number }>;
}
export interface AskBrief { question_id: string; headline: string; answer: string; cached?: boolean; model?: string }
export interface AskAnswer {
  query: string; answer: string | null; headline?: string | null; evidence_strength: string; reviews_considered: number; reviews_matching?: number; citations_dropped_unverifiable?: number; cached?: boolean; model?: string; reason?: string;
  citations: { review_id: string; quote: string; source: string; source_url: string; review_date: string | null; sentiment_label: SentimentName }[];
  usage?: { input_tokens: number | null; output_tokens: number | null; neurons: number | null; seconds: number | null };
}

// ---- analysis of an uploaded CSV ----
export interface UploadEvidence { evidence_id: string; review_id: string; quote: string; source: string | null; source_url: string | null; review_date: string | null; rating: string | null; sentiment: string }
export interface UploadAnalysis {
  upload_id: string; source_file: string | null; generated_at: string; provider: string; model: string; method: string;
  dataset: { rows_in_upload: number; rows_submitted_to_analysis: number; rows_not_analysed_due_to_limit: number; analysis_row_limit: number; reviews_analysed: number; extraction_failed: number; not_a_customer_experience: number; sources: Record<string, number> };
  sentiment: Record<string, { n: number; pct: number }>;
  themes: { theme_id: string; name: string; description: string; review_count: number; pct_of_analysed: number; sentiment: Record<string, number>; labels: string[]; evidence_ids: string[]; rank: number }[];
  positive_experiences: Experience; negative_experiences: Experience; mixed_reviews: number;
  insights: { insight_id: string; title: string; insight: string; evidence_ids: string[] }[];
  opportunities: { opportunity_id: string; name: string; customer_problem: string; related_themes: string[]; why_it_matters: string; suggested_improvement_hypothesis: string; repeat_booking_link_hypothesis: string; impact_score_1_to_5_analyst_judgement: number | null; evidence_ids: string[] }[];
  evidence: UploadEvidence[];
  quality: Record<string, number>;
  usage: { requests: number; successful_requests: number; failed_requests: number; input_tokens: number; output_tokens: number; neurons: number; seconds: number; processing_seconds: number; cache_hits: number | null; by_purpose: Record<string, { requests: number; failed: number; input_tokens: number; output_tokens: number; neurons: number; seconds: number }> };
}
export interface Experience { review_count: number; pct_of_analysed: number; top_themes: { theme: string; review_count: number }[]; most_repeated_phrases: { phrase: string; review_count: number }[]; evidence_ids: string[]; summary: string | null }
export interface UploadAnalysisReview {
  return_class?: string; return_basis?: string; review_id: string; source: string | null; source_url: string | null; sentiment: string; theme_names: string[]; problem: string | null; positive: string | null; evidence_quote: string; extraction_status: string }
export interface AnalysisJob extends UploadJob { progress?: { phase: string; done: number; total: number; message: string }; usage?: UploadAnalysis["usage"]; reused_saved_results?: boolean; result?: { summary?: Record<string, number> } | null }


// ---- golden set ----
export interface GoldenSummary {
  rows: number; analysed: number; match_counts: Record<"Full match" | "Partial match" | "Non-match" | "Not analysed", number>;
  sentiment: { compared: number; agree: number; agreement_pct: number | null; agreement_pct_excluding_mixed: number | null; kappa: number | null; confusion: Record<string, Record<string, number>> };
  return: { compared: number; agree: number; agreement_pct: number | null; agreement_pct_when_both_classified: number | null; both_classified: number; kappa: number | null; confusion: Record<string, Record<string, number>> };
  caution: string;
}
export interface GoldenMeta {
  golden_id: string; name: string; filename: string; created_at: string; primary: boolean; evaluated: boolean; job_status?: string;
  summary: { rows_in_file: number; accepted: number; rejected: number; with_sentiment_label: number; with_return_label: number; with_problem_label: number };
  evaluation_summary?: GoldenSummary;
  column_mapping: Record<string, string>; issues?: { line: number; severity: string; code: string; message: string }[]; job?: AnalysisJob; usage?: UploadAnalysis["usage"];
}
export interface GoldenRow {
  row_id: string; review_id: string; review_text: string; human_sentiment: string | null; human_return: string | null; human_theme: string | null; source_url: string;
  engine_sentiment: string | null; engine_return: string | null; engine_return_basis: string | null; engine_themes: string[]; engine_evidence_quote: string;
  sentiment_match: boolean | null; return_match: boolean | null; match_status: string;
}
