/**
 * Public API origin for application-to-NexPulse telemetry.
 * The project domain is protected by Vercel authentication in this deployment;
 * use the public alias for external service-to-service requests.
 */
export const getNexpulsePublicIngestOrigin = (): string => import.meta.env.PROD
  ? 'https://nexplus-flame.vercel.app'
  : typeof window !== 'undefined'
    ? window.location.origin
    : 'http://localhost:5173';
