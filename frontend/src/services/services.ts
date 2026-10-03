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
