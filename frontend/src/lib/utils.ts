import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'Invalid date';
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(date);
  } catch {
    return 'N/A';
  }
}

export function formatDuration(durationMs: number | null | undefined): string {
  if (durationMs == null) return 'N/A';
  if (durationMs < 1) return '< 1 ms';
  if (durationMs < 1000) return `${Math.round(durationMs)} ms`;
  return `${(durationMs / 1000).toFixed(2)} s`;
}

export type ServiceSignalState = 'inactive' | 'never-connected' | 'receiving' | 'quiet';

/**
 * Signal age alone cannot prove an app is unhealthy. Many serverless and
 * Streamlit services emit telemetry only while handling an active page run.
 */
export function getServiceSignalState(
  isActive: boolean | undefined,
  lastSeenAt: string | null | undefined,
  now = Date.now(),
): ServiceSignalState {
  if (isActive === false) return 'inactive';
  if (!lastSeenAt) return 'never-connected';
  const lastSignalTime = new Date(lastSeenAt).getTime();
  if (!Number.isFinite(lastSignalTime)) return 'never-connected';
  return now - lastSignalTime < 5 * 60 * 1000 ? 'receiving' : 'quiet';
}

export function safeExtractErrorMessage(err: unknown): string {
  if (!err) return 'An unexpected error occurred.';
  if (typeof err === 'string') return err;
  if (err instanceof Error) return err.message;
  if (typeof err === 'object' && 'message' in err && typeof (err as { message: unknown }).message === 'string') {
    return (err as { message: string }).message;
  }
  return 'An unexpected server error occurred.';
}
