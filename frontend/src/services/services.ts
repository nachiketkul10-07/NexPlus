import { apiFetch } from './api';
import { GitHubRepositoryPreview, Service, ServiceCreatePayload } from '../types';

export async function getServicesApi(): Promise<Service[]> {
  return apiFetch<Service[]>('/services', {
    method: 'GET',
  });
}

export async function getServiceByIdApi(serviceId: string): Promise<Service> {
  return apiFetch<Service>(`/services/${serviceId}`, {
    method: 'GET',
  });
}

export async function createServiceApi(payload: ServiceCreatePayload): Promise<Service> {
  return apiFetch<Service>('/services', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function previewGitHubRepositoryApi(
  repositoryUrl: string,
  accessToken?: string,
): Promise<GitHubRepositoryPreview> {
  return apiFetch<GitHubRepositoryPreview>('/services/github/preview', {
    method: 'POST',
    body: JSON.stringify({ repository_url: repositoryUrl, access_token: accessToken || undefined }),
  });
}

export async function rotateServiceIngestKeyApi(serviceId: string): Promise<{ service_id: string; identifier: string; ingest_key: string }> {
  return apiFetch(`/services/${serviceId}/rotate-ingest-key`, { method: 'POST' });
}

export async function deleteServiceApi(serviceId: string): Promise<void> {
  await apiFetch(`/services/${serviceId}`, { method: 'DELETE' });
}
