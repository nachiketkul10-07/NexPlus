import { apiFetch } from './api';
import { TelemetryEvent, Metric, LogEntry } from '../types';

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
