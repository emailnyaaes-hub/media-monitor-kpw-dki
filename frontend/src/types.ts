export type Role = 'admin' | 'analis' | 'pimpinan'
export type Sentiment = 'positif' | 'netral' | 'negatif'
export type Stance = 'upside' | 'netral' | 'downside'
export type Severity = 'info' | 'waspada' | 'kritis'

export interface User {
  username: string
  full_name: string
  role: Role
  role_label: string
}

export interface Delta {
  value: number
  previous: number
  delta_pct?: number | null
  delta_points?: number
}

export interface MentionCard {
  id: number
  title: string
  source_name: string
  source_tier: number
  platform: string
  published_at: string
  stance: Stance
  sentiment: Sentiment
  reach_estimate: number
  risk_score: number
  category: string
  confidence: number
  is_kpw: boolean
  location: string
  status: string
  issue_id: number | null
  url: string
  quotes_bi: boolean
}

export interface MentionDetail extends MentionCard {
  url: string
  author_name: string
  author_handle: string
  text: string
  language: string
  likes: number
  shares: number
  comments: number
  keyword_matches: string[]
  sentiment_score: number
  rationale: string
  policy_relevance: number
  policy_tags: string[]
  spread_velocity: number
  impact_level: string
  credibility: number
  has_public_figure: boolean
  needs_verification: boolean
  verification_note: string
  pic: string
  analyst_note: string
  human_corrected: boolean
  link_note: string
  audit: { actor: string; action: string; old_value: string; new_value: string; created_at: string }[]
}

export interface IssueCard {
  id: number
  code: string
  title: string
  summary: string
  category: string
  stance: Stance
  sentiment: Sentiment
  risk_score: number
  policy_relevance: number
  spread_velocity: number
  impact_level: string
  impact_score: number
  quadrant: string
  status: string
  pic: string
  is_critical: boolean
  is_kpw: boolean
  spike_detected: boolean
  policy_tags: string[]
  started_at: string
  mention_count: number
  last_at: string | null
  x?: number
  y?: number
}

export interface IssueDetail extends IssueCard {
  analyst_note: string
  ai_what: string
  ai_who: string
  ai_sentiment: string
  ai_impact: string
  ai_recommendation: string
  ai_note: string
  timeline: MentionCard[]
  timeline_note: string
}

export interface AlertItem {
  id: number
  title: string
  message: string
  severity: Severity
  triggered_at: string
  is_read: boolean
  issue_id: number | null
}

export interface TrendPoint {
  date: string
  positif: number
  netral: number
  negatif: number
  total: number
  spike: boolean
}

export interface Overview {
  mode: string
  seeded_at: string | null
  disclaimer: string
  period: { from: string; to: string }
  previous_period: { from: string; to: string }
  kpis: {
    total_mention: Delta
    sentiment_pct: { positif: number; netral: number; negatif: number; previous: { positif: number; netral: number; negatif: number } }
    net_sentiment: { value: number; previous: number; delta_points: number }
    reach: Delta
    critical_issues: Delta
  }
  trend: TrendPoint[]
  top_upside: { window_label: string; items: MentionCard[] }
  top_downside: { window_label: string; items: MentionCard[] }
  critical_issue_list: IssueCard[]
  active_alerts: AlertItem[]
}
