import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Overview } from '../pages/Overview';
import { Reports } from '../pages/Reports';
import { getServicesApi } from '../services/services';
import { fetchIncidentsApi } from '../services/incidents';
import { fetchAlertsApi } from '../services/alerts';
import { getTelemetryEventsApi } from '../services/telemetry';

vi.mock('../services/services', () => ({ getServicesApi: vi.fn() }));
vi.mock('../services/incidents', () => ({ fetchIncidentsApi: vi.fn() }));
vi.mock('../services/alerts', () => ({ fetchAlertsApi: vi.fn() }));
vi.mock('../services/telemetry', () => ({ getTelemetryEventsApi: vi.fn() }));
vi.mock('../services/demo', () => ({ runDemoScenarioApi: vi.fn(), DEMO_APP_URL: 'http://localhost' }));
vi.mock('../app/AuthContext', () => ({ useAuth: () => ({ user: { role: 'VIEWER' } }) }));

const services = [
  { id: 'svc-fresh', name: 'Fresh service', environment: 'production', status: 'healthy', is_active: true, last_seen_at: '2026-10-16T11:58:00Z', created_at: '2026-10-01T00:00:00Z' },
  { id: 'svc-old', name: 'Demo Application', environment: 'development', status: 'healthy', is_active: true, last_seen_at: '2026-10-14T00:00:00Z', created_at: '2026-10-01T00:00:00Z' },
  { id: 'svc-never', name: 'Never connected', environment: 'production', status: 'healthy', is_active: true, last_seen_at: null, created_at: '2026-10-01T00:00:00Z' },
] as never[];

const events = Array.from({ length: 16 }, (_, index) => ({
  id: index + 1,
  service_id: 'svc-fresh',
  occurred_at: '2026-10-16T12:00:00Z',
  status_code: index < 3 ? 500 : 200,
  duration_ms: 12,
  outcome: index < 3 ? 'failure' : 'success',
})) as never[];

describe('UI data consistency', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-16T12:00:00Z'));
    vi.mocked(getServicesApi).mockResolvedValue(services);
    vi.mocked(fetchIncidentsApi).mockResolvedValue([]);
    vi.mocked(fetchAlertsApi).mockResolvedValue([]);
    vi.mocked(getTelemetryEventsApi).mockResolvedValue(events);
  });

  afterEach(() => vi.restoreAllMocks());

  it('counts only services receiving within five minutes and labels idle services quiet', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);

    expect(await screen.findByText('Receiving Services')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Quiet · no recent signal')).toBeInTheDocument());
    expect(screen.getAllByText('Never connected')).toHaveLength(2);
    expect(screen.getByText('Receiving', { selector: 'span' })).toBeInTheDocument();
    const receivingLabel = screen.getByText('Receiving Services');
    expect(receivingLabel.parentElement?.querySelector('div')?.textContent).toBe('1');
  });

  it('labels the sampled HTTP request error calculation and separates ingestion rejection', async () => {
    render(<Reports />);

    expect(await screen.findByText('Observed HTTP Error Rate')).toBeInTheDocument();
    expect(screen.getByText('18.75%')).toBeInTheDocument();
    expect(screen.getByText(/Includes demo failures; excludes rejected telemetry ingestion\./)).toBeInTheDocument();
  });
});
