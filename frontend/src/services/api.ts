export class ApiError extends Error {
  public status: number;
  public detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message = 'Session expired. Please log in again.', detail?: unknown) {
    super(401, message, detail);
    this.name = 'UnauthorizedError';
  }
}

export class ForbiddenError extends ApiError {
  constructor(message = 'Access denied. You do not have permission to view or modify this resource.') {
    super(403, message);
    this.name = 'ForbiddenError';
  }
}

export class RateLimitError extends ApiError {
  constructor(message = 'Too many requests. Please try again shortly.') {
    super(429, message);
    this.name = 'RateLimitError';
  }
}

export class ServerError extends ApiError {
  constructor(message = 'The NexPulse service is currently experiencing technical difficulties.') {
    super(500, message);
    this.name = 'ServerError';
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

let onUnauthorizedCallback: (() => void) | null = null;

export function setOnUnauthorizedCallback(callback: () => void) {
  onUnauthorizedCallback = callback;
}

interface FetchOptions extends RequestInit {
  timeoutMs?: number;
  skipUnauthorizedHandler?: boolean;
  preserveUnauthorizedMessage?: boolean;
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const {
    timeoutMs = 15000,
    headers = {},
    skipUnauthorizedHandler = false,
    preserveUnauthorizedMessage = false,
    ...customConfig
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...(headers as Record<string, string>),
  };

  const cleanEndpoint = endpoint.startsWith('/api/v1/')
    ? endpoint.substring(7)
    : endpoint === '/api/v1'
    ? '/'
    : endpoint;

  const url = cleanEndpoint.startsWith('http')
    ? cleanEndpoint
    : `${API_BASE_URL}${cleanEndpoint.startsWith('/') ? '' : '/'}${cleanEndpoint}`;

  try {
    const response = await fetch(url, {
      ...customConfig,
      headers: requestHeaders,
      credentials: 'include',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.status === 401) {
      if (preserveUnauthorizedMessage) {
        let message = 'Invalid email or password.';
        let detail: unknown;
        try {
          const body = await response.json();
          detail = body;
          const serverMessage = body?.error?.message || body?.detail;
          if (typeof serverMessage === 'string' && serverMessage.trim()) {
            message = serverMessage;
          }
        } catch {
          // Keep the safe login-specific fallback for non-JSON responses.
        }
        throw new UnauthorizedError(message, detail);
      }
      if (!skipUnauthorizedHandler && onUnauthorizedCallback) {
        onUnauthorizedCallback();
      }
      throw new UnauthorizedError();
    }

    if (response.status === 403) {
      throw new ForbiddenError();
    }

    if (response.status === 429) {
      throw new RateLimitError();
    }

    if (response.status >= 500) {
      throw new ServerError();
    }

    if (!response.ok) {
      let errorMessage = `HTTP error ${response.status}`;
      let errorDetail: unknown = null;
      try {
        const errorJson = await response.json();
        if (errorJson.error) {
          if (errorJson.error.message) {
            errorMessage = errorJson.error.message;
          }
          if (Array.isArray(errorJson.error.details) && errorJson.error.details.length > 0) {
            const detailMsgs = errorJson.error.details
              .map((d: any) => d.message || d.msg || String(d))
              .join('; ');
            if (detailMsgs) {
              errorMessage = detailMsgs;
            }
            errorDetail = errorJson.error.details;
          }
        } else if (errorJson.detail) {
          if (typeof errorJson.detail === 'string') {
            errorMessage = errorJson.detail;
          } else if (Array.isArray(errorJson.detail) && errorJson.detail[0]?.msg) {
            errorMessage = errorJson.detail[0].msg;
            errorDetail = errorJson.detail;
          }
        }
      } catch {
        // Fallback for non-JSON response body
      }
      throw new ApiError(response.status, errorMessage, errorDetail);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(408, 'Request timed out. Please check network connectivity and retry.');
    }

    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(0, 'Unable to connect to NexPulse backend service. Verify server status.');
    }

    throw new ApiError(500, error instanceof Error ? error.message : 'An unexpected request error occurred.');
  }
}
