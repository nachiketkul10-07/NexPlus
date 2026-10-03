import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render as renderRTL, screen as screenRTL, waitFor as waitForRTL } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Incidents } from '../pages/Incidents';
import * as incidentsService from '../services/incidents';
import * as servicesService from '../services/services';
import { AuthProvider } from '../app/AuthContext';

vi.mock('../services/incidents');
vi.mock('../services/services');

describe('Incidents Page Component', () => {
  const mockIncidents = [
    {
      id: 'inc-1111-2222',
      service_id: '33333333-3333-3333-3333-333333333333',
      title: 'High HTTP 500 Rate on Demo Application',
      description: 'Error rate crossed 0.10 threshold',
      severity: 'critical' as const,
      status: 'open' as const,
      opened_at: new Date().toISOString(),
      detected_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      service_name: 'Demo Application',
      originating_alert_rule_name: 'High HTTP 500 Rate',
      evidence: { error_rate: 0.25 },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(servicesService, 'getServicesApi').mockResolvedValue([
      {
        id: '33333333-3333-3333-3333-333333333333',
        name: 'Demo Application',
        slug: 'demo-app',
        service_type: 'api',
        environment: 'development',
        status: 'healthy',
        created_at: new Date().toISOString(),
      },
    ]);
    vi.spyOn(incidentsService, 'fetchIncidentsApi').mockResolvedValue(mockIncidents);
    vi.spyOn(incidentsService, 'fetchIncidentDetailApi').mockResolvedValue(mockIncidents[0]);
    vi.spyOn(incidentsService, 'fetchIncidentEventsApi').mockResolvedValue([
      {
        id: 1,
        incident_id: 'inc-1111-2222',
        event_type: 'INCIDENT_CREATED',
        message: 'Incident created automatically',
        created_at: new Date().toISOString(),
      },
    ]);
  });

  it('renders incidents header and loads list from API', async () => {
    renderRTL(
      <AuthProvider>
        <BrowserRouter>
          <Incidents />
        </BrowserRouter>
      </AuthProvider>
    );

    expect(screenRTL.getByText('Incidents')).toBeInTheDocument();
    await waitForRTL(() => {
      expect(screenRTL.getByText('High HTTP 500 Rate on Demo Application')).toBeInTheDocument();
    });
  });
});
