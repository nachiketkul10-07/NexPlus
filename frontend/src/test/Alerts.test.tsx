import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render as renderRTL, screen as screenRTL, waitFor as waitForRTL } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Alerts } from '../pages/Alerts';
import * as alertsService from '../services/alerts';
import * as servicesService from '../services/services';
import { AuthProvider } from '../app/AuthContext';

vi.mock('../services/alerts');
vi.mock('../services/services');

describe('Alerts Page Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders alert engine header and loads backend rules and alerts', async () => {
    vi.spyOn(alertsService, 'fetchAlertRulesApi').mockResolvedValue([
      {
        id: 'rule-123',
        name: 'High Error Rate Rule',
        metric_name: 'error_rate',
        operator: '>',
        threshold: 0.1,
        window_seconds: 60,
        severity: 'critical',
        create_incident: true,
        cooldown_seconds: 300,
        enabled: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    vi.spyOn(alertsService, 'fetchAlertsApi').mockResolvedValue([
      {
        id: 'alert-456',
        rule_id: 'rule-123',
        service_id: 'svc-789',
        status: 'active',
        severity: 'critical',
        current_value: 0.25,
        threshold_value: 0.1,
        triggered_at: new Date().toISOString(),
        last_seen_at: new Date().toISOString(),
        rule_name: 'High Error Rate Rule',
        service_name: 'Demo Application',
      },
    ]);

    vi.spyOn(servicesService, 'getServicesApi').mockResolvedValue([
      {
        id: 'svc-789',
        name: 'Demo Application',
        slug: 'demo-app',
        service_type: 'web',
        environment: 'development',
        status: 'healthy',
        created_at: new Date().toISOString(),
      },
    ]);

    renderRTL(
      <BrowserRouter>
        <AuthProvider>
          <Alerts />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitForRTL(() => {
      expect(screenRTL.getByText('Alert Engine & Rule Configuration')).toBeInTheDocument();
    });

    expect(screenRTL.getAllByText('High Error Rate Rule').length).toBeGreaterThanOrEqual(1);
    expect(screenRTL.getByText('TRIGGERED ALERTS (1)')).toBeInTheDocument();
    expect(screenRTL.getByText('CONFIGURED ALERT RULES (1)')).toBeInTheDocument();
  });
});
