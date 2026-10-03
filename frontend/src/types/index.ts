export type UserRole = 'ADMIN' | 'OPERATOR' | 'VIEWER' | 'ENGINEER';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type ServiceStatus = 'healthy' | 'degraded' | 'critical' | 'offline' | 'unknown';

export interface Service {
  id: string;
  identifier?: string;
  /** Legacy display fields may exist in older test fixtures or API deployments. */
  slug?: string;
  service_type?: string;
  name: string;
  environment: string;
  base_url?: string | null;
  repository_url?: string | null;
  health_path?: string;
  status: ServiceStatus;
  description?: string | null;
  last_seen_at?: string | null;
  created_at: string;
  ingest_key?: string; // Returned only once upon registration
}

export interface ServiceCreatePayload {
  identifier: string;
  name: string;
  environment?: string;
  base_url?: string;
  health_path?: string;
  repository_url?: string;
}

export interface GitHubRepositoryPreview {
  full_name: string;
  repository_url: string;
  description?: string | null;
  default_branch: string;
  language?: string | null;
  private: boolean;
  archived: boolean;
  manifest_files: string[];
}

export interface TelemetryEvent {
  id: number;
  service_id: string;
  request_id?: string | null;
  occurred_at: string;
  method?: string | null;
  endpoint?: string | null;
  status_code?: number | null;
  duration_ms?: number | null;
  outcome: string;
  error_type?: string | null;
  error_message?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface Metric {
  id: number;
  service_id: string;
  metric_name: string;
  value: number;
  window_seconds: number;
  recorded_at: string;
}

export interface LogEntry {
  id: number;
  service_id: string;
  occurred_at: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL' | 'FATAL';
  message: string;
  request_id?: string | null;
  trace_id?: string | null;
  stack_trace?: string | null;
  metadata?: Record<string, unknown> | null;
}

export type AlertSeverity = 'critical' | 'warning' | 'info';
export type AlertStatus = 'active' | 'resolved' | 'suppressed';

export interface AlertRule {
  id: string;
  name: string;
  metric_name: string;
  operator: string;
  threshold: number;
  window_seconds: number;
  severity: AlertSeverity;
  create_incident: boolean;
  cooldown_seconds: number;
  enabled: boolean;
  service_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertRuleCreatePayload {
  name: string;
  metric_name: string;
  operator: string;
  threshold: number;
  window_seconds?: number;
  severity: AlertSeverity;
  create_incident?: boolean;
  cooldown_seconds?: number;
  enabled?: boolean;
  service_id?: string | null;
}

export interface Alert {
  id: string;
  rule_id: string;
  service_id: string;
  status: AlertStatus;
  severity: AlertSeverity;
  current_value?: number | null;
  threshold_value?: number | null;
  triggered_at: string;
  last_seen_at: string;
  resolved_at?: string | null;
  evidence?: Record<string, unknown> | null;
  rule_name?: string | null;
  service_name?: string | null;
}

export interface AlertEvaluationSummary {
  rules_evaluated: number;
  alerts_triggered: number;
  alerts_updated: number;
  alerts_resolved: number;
  evaluated_at: string;
}

export type IncidentStatus = 'open' | 'investigating' | 'resolved';

export interface Incident {
  id: string;
  service_id: string;
  alert_id?: string | null;
  title: string;
  description?: string | null;
  severity: AlertSeverity;
  status: IncidentStatus;
  assignee_user_id?: string | null;
  detected_at: string;
  opened_at: string;
  investigating_at?: string | null;
  resolved_at?: string | null;
  resolution_note?: string | null;
  created_at: string;
  updated_at: string;
  service_name?: string | null;
  assignee_email?: string | null;
  assignee_name?: string | null;
  originating_alert_rule_name?: string | null;
  evidence?: Record<string, unknown> | null;
}

export interface IncidentUpdatePayload {
  status?: IncidentStatus;
  assignee_user_id?: string | null;
  resolution_note?: string;
}

export interface IncidentEvent {
  id: number;
  incident_id: string;
  event_type: string;
  actor_user_id?: string | null;
  actor_name?: string | null;
  message: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}
export interface EvidenceItem {
  source_type: string;
  source_reference?: string | null;
  observation: string;
}

export interface PossibleCause {
  statement: string;
  supporting_evidence: string[];
  confidence: 'high' | 'medium' | 'low';
}

export interface AIAnalysisResponse {
  id: string;
  incident_id: string;
  provider: string;
  model_name: string;
  prompt_version: string;
  status: 'generated' | 'fallback' | 'unavailable';
  summary: string;
  evidence: EvidenceItem[];
  possible_causes: PossibleCause[];
  next_checks: string[];
  limitations_note: string;
  created_at: string;
}



export interface ApiErrorResponse {
  status_code: number;
  message: string;
  detail?: unknown;
}

export interface AuthState {
  user: User | null;
  hasSession: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
