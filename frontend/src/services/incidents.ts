import { apiFetch } from './api';
import { Incident, IncidentEvent, IncidentUpdatePayload, AIAnalysisResponse } from '../types';

export async function fetchIncidentsApi(filters?: {
  service_id?: string;
  status?: string;
  severity?: string;
  assignee_user_id?: string;
  limit?: number;
  offset?: number;
}): Promise<Incident[]> {
  const queryParts: string[] = [];
  if (filters?.service_id) queryParts.push(`service_id=${encodeURIComponent(filters.service_id)}`);
  if (filters?.status) queryParts.push(`status=${encodeURIComponent(filters.status)}`);
  if (filters?.severity) queryParts.push(`severity=${encodeURIComponent(filters.severity)}`);
  if (filters?.assignee_user_id) queryParts.push(`assignee_user_id=${encodeURIComponent(filters.assignee_user_id)}`);
  if (filters?.limit) queryParts.push(`limit=${filters.limit}`);
  if (filters?.offset) queryParts.push(`offset=${filters.offset}`);

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
  return apiFetch<Incident[]>(`/incidents${queryString}`);
}

export async function fetchIncidentDetailApi(incidentId: string): Promise<Incident> {
  return apiFetch<Incident>(`/incidents/${incidentId}`);
}

export async function updateIncidentApi(
  incidentId: string,
  payload: IncidentUpdatePayload
): Promise<Incident> {
  return apiFetch<Incident>(`/incidents/${incidentId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function fetchIncidentEventsApi(incidentId: string): Promise<IncidentEvent[]> {
  return apiFetch<IncidentEvent[]>(`/incidents/${incidentId}/events`);
}

export async function addIncidentNoteApi(
  incidentId: string,
  message: string,
  metadata?: Record<string, unknown>
): Promise<IncidentEvent> {
  return apiFetch<IncidentEvent>(`/incidents/${incidentId}/events`, {
    method: 'POST',
    body: JSON.stringify({ message, metadata }),
  });
}

export async function generateAIAnalysisApi(
  incidentId: string,
  forceRefresh: boolean = false
): Promise<AIAnalysisResponse> {
  return apiFetch<AIAnalysisResponse>(`/incidents/${incidentId}/ai-analysis`, {
    method: 'POST',
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
}

export async function getLatestAIAnalysisApi(incidentId: string): Promise<AIAnalysisResponse> {
  return apiFetch<AIAnalysisResponse>(`/incidents/${incidentId}/ai-analysis`);
}
