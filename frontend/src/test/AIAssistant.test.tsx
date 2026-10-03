import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render as renderRTL, screen as screenRTL, waitFor as waitForRTL } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AIAssistant } from '../pages/AIAssistant';
import { AIAnalysisPanel } from '../components/ui/AIAnalysisPanel';
import * as incidentsService from '../services/incidents';
import { AuthProvider } from '../app/AuthContext';

vi.mock('../services/incidents');

describe('AI Assistant Component Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders AIAnalysisPanel with generated AI status and structured content', async () => {
    vi.spyOn(incidentsService, 'getLatestAIAnalysisApi').mockResolvedValue({
      id: 'analysis-123',
      incident_id: 'inc-456',
      provider: 'groq',
      model_name: 'llama-3.3-70b-versatile',
      prompt_version: 'v1',
      status: 'generated',
      summary: 'Elevated HTTP 500 error rate observed on Demo Application.',
      evidence: [
        {
          source_type: 'alert',
          source_reference: 'Rule: High Error Rate',
          observation: 'Error rate reached 0.25 (threshold: 0.10).',
        },
      ],
      possible_causes: [
        {
          statement: 'PostgreSQL connection pool exhaustion.',
          supporting_evidence: ['Rule: High Error Rate'],
          confidence: 'high',
        },
      ],
      next_checks: ['Verify connection pool active queries.'],
      limitations_note: 'Advisory analysis only.',
      created_at: new Date().toISOString(),
    });

    renderRTL(
      <BrowserRouter>
        <AuthProvider>
          <AIAnalysisPanel incidentId="inc-456" />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitForRTL(() => {
      expect(screenRTL.getByText('Incident analysis')).toBeInTheDocument();
      expect(screenRTL.getByText('LIVE AI')).toBeInTheDocument();
    });

    expect(screenRTL.getByText('Elevated HTTP 500 error rate observed on Demo Application.')).toBeInTheDocument();
    expect(screenRTL.getByText('PostgreSQL connection pool exhaustion.')).toBeInTheDocument();
    expect(screenRTL.getByText('high confidence')).toBeInTheDocument();
    expect(screenRTL.getByText('Verify connection pool active queries.')).toBeInTheDocument();
  });

  it('renders AI Assistant workspace page and loads incident dropdown', async () => {
    vi.spyOn(incidentsService, 'fetchIncidentsApi').mockResolvedValue([
      {
        id: 'inc-456',
        service_id: 'svc-789',
        title: 'Database Spike on Order API',
        severity: 'critical',
        status: 'open',
        detected_at: new Date().toISOString(),
        opened_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    vi.spyOn(incidentsService, 'getLatestAIAnalysisApi').mockResolvedValue({
      id: 'analysis-123',
      incident_id: 'inc-456',
      provider: 'groq',
      model_name: 'llama-3.3-70b-versatile',
      prompt_version: 'v1',
      status: 'fallback',
      summary: 'Fallback deterministic summary.',
      evidence: [],
      possible_causes: [],
      next_checks: [],
      limitations_note: 'Fallback mode active.',
      created_at: new Date().toISOString(),
    });

    renderRTL(
      <BrowserRouter>
        <AuthProvider>
          <AIAssistant />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitForRTL(() => {
      expect(screenRTL.getByText('NexPulse AI Assistant')).toBeInTheDocument();
      expect(screenRTL.getByText('Incident under investigation')).toBeInTheDocument();
    });
  });
});
