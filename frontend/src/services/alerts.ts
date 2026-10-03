import { apiFetch } from './api';
import { AlertRule, Alert, AlertRuleCreatePayload, AlertEvaluationSummary } from '../types';

export async function fetchAlertRulesApi(serviceId?: string): Promise<AlertRule[]> {
  const query = serviceId ? `?service_id=${encodeURIComponent(serviceId)}` : '';
  return apiFetch<AlertRule[]>(`/alerts/rules${query}`);
}

export async function fetchAlertsApi(params?: {
  service_id?: string;
  status?: string;
  severity?: string;
  limit?: number;
}): Promise<Alert[]> {
  const queryParts: string[] = [];
  if (params?.service_id) queryParts.push(`service_id=${encodeURIComponent(params.service_id)}`);
  if (params?.status) queryParts.push(`status=${encodeURIComponent(params.status)}`);
  if (params?.severity) queryParts.push(`severity=${encodeURIComponent(params.severity)}`);
  if (params?.limit) queryParts.push(`limit=${params.limit}`);

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
  return apiFetch<Alert[]>(`/alerts${queryString}`);
}

export async function createAlertRuleApi(payload: AlertRuleCreatePayload): Promise<AlertRule> {
  return apiFetch<AlertRule>('/alerts/rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAlertRuleApi(
  ruleId: string,
  payload: Partial<AlertRuleCreatePayload>
): Promise<AlertRule> {
  return apiFetch<AlertRule>(`/alerts/rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteAlertRuleApi(ruleId: string): Promise<{ message: string; rule_id: string }> {
  return apiFetch<{ message: string; rule_id: string }>(`/alerts/rules/${ruleId}`, {
    method: 'DELETE',
  });
}

export async function triggerEvaluationApi(serviceId?: string, ruleId?: string): Promise<AlertEvaluationSummary> {
  const queryParts: string[] = [];
  if (serviceId) queryParts.push(`service_id=${encodeURIComponent(serviceId)}`);
  if (ruleId) queryParts.push(`rule_id=${encodeURIComponent(ruleId)}`);
  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';

  return apiFetch<AlertEvaluationSummary>(`/alerts/evaluate${queryString}`, {
    method: 'POST',
  });
}
