import { apiFetch } from './api';
import { User, UserRole } from '../types';

export async function loginApi(email: string, password: string): Promise<User> {
  const response = await apiFetch<{ user: User }>('/auth/session', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
    }),
  });
  return response.user;
}

export async function registerApi(
  email: string,
  password: string,
  fullName: string,
  role: UserRole = 'OPERATOR'
): Promise<User> {
  return apiFetch<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
      full_name: fullName,
      role,
    }),
  });
}

export async function getCurrentUserApi(): Promise<User> {
  return apiFetch<User>('/auth/me', {
    method: 'GET',
  });
}

export async function logoutApi(): Promise<void> {
  await apiFetch<{ message: string }>('/auth/session/logout', { method: 'POST', skipUnauthorizedHandler: true });
}
