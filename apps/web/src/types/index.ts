export interface User {
  id: string;
  full_name: string;
  email: string;
  status: string;
  roles: string[];
  last_login_at: string | null;
}

export interface SeismicEvent {
  id: string;
  external_id: string;
  source_id: string;
  occurred_at: string;
  latitude: number;
  longitude: number;
  magnitude: number | null;
  magnitude_type: string | null;
  depth_km: number | null;
  place: string | null;
  region: string | null;
  source_url: string | null;
  received_at: string;
  review_status: string;
}

export interface DataSource {
  id: string;
  name: string;
  organization: string;
  base_url: string;
  status: string;
  enabled: boolean;
  license: string;
  frequency_minutes: number;
  last_sync_at: string | null;
  last_success_at: string | null;
  last_latency_ms: number | null;
}

export interface DashboardSummary {
  total_events: number;
  events_last_24h: number;
  events_last_7d: number;
  max_magnitude_7d: number | null;
  avg_depth: number | null;
  median_depth: number | null;
  last_sync_at: string | null;
  active_alerts: number;
  sources: DataSource[];
  period_start: string | null;
  period_end: string | null;
  period_max_magnitude: number | null;
  period_avg_depth: number | null;
}

export interface Experiment {
  id: string;
  name: string;
  task_type: "classification" | "regression";
  algorithm: string;
  dataset_id: string | null;
  metrics: Record<string, unknown>;
  validation_spec: Record<string, unknown>;
  status: string;
  limitations: string;
  created_at: string;
  artifact_uri: string | null;
}

export interface Model {
  id: string;
  experiment_id: string;
  version: number;
  status: string;
  limitations: string;
  created_at: string;
  approved_at: string | null;
}

export interface Estimate {
  id: string;
  model_id: string;
  area_code: string;
  metric_name: string;
  value: number;
  lower_bound: number | null;
  upper_bound: number | null;
  window_start: string | null;
  window_end: string | null;
  calculated_at: string;
  disclaimer: string;
  is_experimental: boolean;
}

export interface ConfigDefinition {
  key: string;
  value: number | string | boolean;
  default: number | string | boolean;
  kind: string;
  minimum: number | null;
  maximum: number | null;
  description: string;
  group: string;
  modified: boolean;
}

export interface ConfigResponse {
  definitions: ConfigDefinition[];
  last_updated_at: string | null;
  last_updated_by: string | null;
}

export interface AlertRule {
  id: string;
  name: string;
  condition_json: Record<string, unknown>;
  severity: string;
  channels: string[];
  cooldown_seconds: number;
  requires_approval: boolean;
  enabled: boolean;
  last_triggered_at: string | null;
}

export interface Alert {
  id: string;
  event_id: string | null;
  rule_id: string | null;
  severity: string;
  title: string;
  message: string;
  source_url: string | null;
  status: string;
  created_at: string;
}

export interface Delivery {
  id: string;
  channel: string;
  status: string;
  attempts: number;
  delivered_at: string | null;
  error_code: string | null;
}

export interface ReportJob {
  id: string;
  report_type: string;
  filters_json: Record<string, unknown>;
  status: string;
  file_ref: string | null;
  error_summary: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface AuditLog {
  id: string;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
  occurred_at: string;
  result: string;
  ip: string | null;
}

export interface Dataset {
  id: string;
  name: string;
  version: number;
  row_count: number;
  period_start: string | null;
  period_end: string | null;
  quality_report: Record<string, unknown>;
  created_at: string;
}
