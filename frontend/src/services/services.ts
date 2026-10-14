import { apiFetch } from './api';
import { Service, ServiceCreatePayload } from '../types';

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

export async function rotateServiceIngestKeyApi(serviceId: string): Promise<{ service_id: string; identifier: string; ingest_key: string }> {
  return apiFetch(`/services/${serviceId}/rotate-ingest-key`, { method: 'POST' });
}

export async function deleteServiceApi(serviceId: string): Promise<void> {
  await apiFetch(`/services/${serviceId}`, { method: 'DELETE' });
}

export async function setServiceActiveApi(serviceId: string, isActive: boolean): Promise<Service> {
  return apiFetch<Service>(`/services/${serviceId}/status?is_active=${isActive}`, { method: 'PATCH' });
}

export async function revokeServiceIngestKeyApi(serviceId: string): Promise<void> {
  await apiFetch(`/services/${serviceId}/revoke-ingest-key`, { method: 'POST' });
}
