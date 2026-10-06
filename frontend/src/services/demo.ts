export interface DemoScenarioResult {
  status: 'completed';
  requests_generated: number;
  successful_requests: number;
  failed_requests: number;
  slow_requests: number;
  telemetry_accepted: number;
  telemetry_failed: number;
  telemetry_failure_statuses: number[];
}

const defaultDemoUrl = import.meta.env.PROD ? '/demo' : 'http://127.0.0.1:8001';
export const DEMO_APP_URL = (import.meta.env.VITE_DEMO_APP_URL || defaultDemoUrl).replace(/\/+$/, '');

/** Triggers the local monitored demo app without forwarding the NexPulse session token. */
export async function runDemoScenarioApi(): Promise<DemoScenarioResult> {
  let response: Response;
  try {
    response = await fetch(`${DEMO_APP_URL}/api/demo/run`, { method: 'POST', headers: { Accept: 'application/json' } });
  } catch {
    throw new Error(`Could not reach the demo app at ${DEMO_APP_URL}. Start demo-app on port 8001 and try again.`);
  }
  if (!response.ok) throw new Error(`Demo traffic could not be generated (HTTP ${response.status}).`);
  const result = await response.json() as DemoScenarioResult;
  if (result.telemetry_failed > 0) {
    const rejectedStatuses = result.telemetry_failure_statuses.join(', ');
    if (result.telemetry_failure_statuses.includes(401)) {
      throw new Error(`Demo generated ${result.requests_generated} requests, but NexPulse rejected telemetry authentication (401). Update PULSEOPS_INGEST_KEY in the Vercel Production environment to the current Demo Application ingestion key, then redeploy.`);
    }
    throw new Error(`Demo generated ${result.requests_generated} requests, but ${result.telemetry_failed} telemetry events were not accepted${rejectedStatuses ? ` (HTTP ${rejectedStatuses})` : ''}. Check the demo service's NexPulse URL and credentials.`);
  }
  if (result.telemetry_accepted === 0) {
    throw new Error('Demo generated requests, but no telemetry events were accepted. Check that telemetry is enabled and the demo service is configured.');
  }
  return result;
}
