import { apiFetch } from './api';
import { TelemetryEvent, Metric, LogEntry } from '../types';

export async function sendConnectionTestApi(serviceId: string, identifier: string, ingestKey: string): Promise<{ status: string; accepted_count: number }> {
  return apiFetch('/telemetry/events', {
    method: 'POST',
    headers: { 'X-Ingest-Key': ingestKey },
    body: JSON.stringify({
      service_id: identifier,
      method: 'GET',
      endpoint: '/nexpulse/connection-check',
      status_code: 200,
      duration_ms: 0,
      outcome: 'success',
      metadata: { source: 'nexpulse-connection-test', service_uuid: serviceId },
    }),
  });
}

export interface TelemetryQueryParams {
  service_id?: string;
  limit?: number;
  offset?: number;
  level?: string;
}

export async function getTelemetryEventsApi(params: TelemetryQueryParams = {}): Promise<TelemetryEvent[]> {
  const query = new URLSearchParams();
  if (params.service_id) query.append('service_id', params.service_id);
  if (params.limit) query.append('limit', params.limit.toString());
  if (params.offset) query.append('offset', params.offset.toString());

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiFetch<TelemetryEvent[]>(`/telemetry/events${queryString}`, {
    method: 'GET',
  });
}

export async function getTelemetryMetricsApi(params: TelemetryQueryParams = {}): Promise<Metric[]> {
  const query = new URLSearchParams();
  if (params.service_id) query.append('service_id', params.service_id);
  if (params.limit) query.append('limit', params.limit.toString());

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiFetch<Metric[]>(`/telemetry/metrics${queryString}`, {
    method: 'GET',
  });
}

export async function getTelemetryLogsApi(params: TelemetryQueryParams = {}): Promise<LogEntry[]> {
  const query = new URLSearchParams();
  if (params.service_id) query.append('service_id', params.service_id);
  if (params.level) query.append('level', params.level);
  if (params.limit) query.append('limit', params.limit.toString());
  if (params.offset) query.append('offset', params.offset.toString());

  const queryString = query.toString() ? `?${query.toString()}` : '';
  return apiFetch<LogEntry[]>(`/telemetry/logs${queryString}`, {
    method: 'GET',
  });
}
