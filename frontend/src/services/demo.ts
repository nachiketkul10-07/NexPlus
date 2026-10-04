export interface DemoScenarioResult {
  status: 'completed';
  requests_generated: number;
  successful_requests: number;
  failed_requests: number;
  slow_requests: number;
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
  return response.json() as Promise<DemoScenarioResult>;
}
