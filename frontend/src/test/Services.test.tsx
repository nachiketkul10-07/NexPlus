import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Services } from '../pages/Services';
import { createServiceApi, getServicesApi } from '../services/services';
import { sendConnectionTestApi } from '../services/telemetry';

vi.mock('../services/services', () => ({ getServicesApi: vi.fn(), createServiceApi: vi.fn(), deleteServiceApi: vi.fn() }));
vi.mock('../services/telemetry', () => ({ sendConnectionTestApi: vi.fn() }));
vi.mock('../app/AuthContext', () => ({ useAuth: () => ({ user: { role: 'ADMIN' } }) }));

describe('application service onboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getServicesApi).mockResolvedValue([]);
    vi.mocked(sendConnectionTestApi).mockResolvedValue({ status: 'accepted', accepted_count: 1 });
    vi.mocked(createServiceApi).mockResolvedValue({
      id: 'service-id', identifier: 'study-planner', name: 'Study Planner', environment: 'production',
      status: 'unknown', created_at: new Date().toISOString(), ingest_key: 'pik_live_one_time_key',
    });
  });

  it('creates a service, displays connection settings, and confirms a stored test signal', async () => {
    render(<MemoryRouter><Services /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Connect application' }));
    fireEvent.change(screen.getByLabelText('Application name'), { target: { value: 'Study Planner' } });
    expect(screen.getByLabelText('Service identifier')).toHaveValue('study-planner');
    fireEvent.click(screen.getByRole('button', { name: 'Create service and get connection key' }));

    await waitFor(() => expect(createServiceApi).toHaveBeenCalledWith(expect.objectContaining({ identifier: 'study-planner', name: 'Study Planner' })));
    expect(await screen.findByText('pik_live_one_time_key')).toBeInTheDocument();
    expect(screen.getByText(/NEXPULSE_SERVICE_ID = "study-planner"/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Send test event' }));
    expect(await screen.findByText('Connection accepted. 1 event persisted.')).toBeInTheDocument();
    expect(sendConnectionTestApi).toHaveBeenCalledWith('service-id', 'study-planner', 'pik_live_one_time_key');
  });
});
