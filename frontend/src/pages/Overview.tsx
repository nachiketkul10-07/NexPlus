import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../app/AuthContext';
import { PageHeader } from '../components/layout/PageHeader';
import { getServicesApi } from '../services/services';
import { getTelemetryEventsApi } from '../services/telemetry';
import { fetchIncidentsApi } from '../services/incidents';
import { fetchAlertsApi } from '../services/alerts';
import { Service, TelemetryEvent, Incident, Alert } from '../types';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { formatDate, formatDuration, safeExtractErrorMessage } from '../lib/utils';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { runDemoScenarioApi, DemoScenarioResult, DEMO_APP_URL } from '../services/demo';
import { triggerEvaluationApi } from '../services/alerts';
import { AlertEvaluationSummary } from '../types';

export const Overview: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role.toLowerCase() === 'admin';
  const demoToolsEnabled = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEMO_TOOLS === 'true';
  const [services, setServices] = useState<Service[]>([]);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isRunningDemo, setIsRunningDemo] = useState(false);
  const [demoMessage, setDemoMessage] = useState<string | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);
  const [demoResult, setDemoResult] = useState<{ traffic: DemoScenarioResult; evaluation: AlertEvaluationSummary } | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [s, e, inc, alt] = await Promise.all([
        getServicesApi(),
        getTelemetryEventsApi({ limit: 15 }),
        fetchIncidentsApi({ limit: 5 }),
        fetchAlertsApi({ limit: 5 }),
      ]);
      setServices(s);
      setEvents(e);
      setIncidents(inc);
      setAlerts(alt);
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRunDemo = async () => {
    setIsRunningDemo(true);
    setDemoError(null);
    setDemoMessage(null);
    try {
      const traffic = await runDemoScenarioApi();
      const evaluation = await triggerEvaluationApi();
      setDemoResult({ traffic, evaluation });
      setDemoMessage(`${traffic.telemetry_accepted} telemetry events accepted and alert rules evaluated.`);
      await fetchData();
    } catch (err) {
      setDemoError(safeExtractErrorMessage(err));
    } finally {
      setIsRunningDemo(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="System Overview" description="Operational telemetry summary." />
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="System Overview" description="Operational telemetry summary." />
        <ErrorState message={error} onRetry={fetchData} />
      </div>
    );
  }

  const openIncidents = incidents.filter((i) => i.status !== 'resolved');
  const activeAlerts = alerts.filter((a) => a.status === 'active');

  return (
    <div className="space-y-6">
      <PageHeader title="Operational Control Center" description="Real-time telemetry summary, monitored service health, active alerts, and incident tracking." />

      {isAdmin && demoToolsEnabled && (
        <section className="rounded border border-[#333333] bg-[#1F1F1F] p-5" aria-labelledby="demo-control-title">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-[10px] font-mono font-semibold uppercase tracking-wider text-[#E50039]">End-to-end showcase</p>
              <h2 id="demo-control-title" className="mt-1 text-sm font-semibold font-mono">Demo Application</h2>
              <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[#A7A7A7]">Generate healthy, slow, and failing requests to populate telemetry, metrics, logs, alerts, and incident evidence.</p>
            </div>
            <div className="flex items-center gap-3">
              <a className="text-xs text-[#A7A7A7] transition-colors hover:text-[#F7F7F7]" href={`${DEMO_APP_URL}/docs`} target="_blank" rel="noreferrer">API explorer ↗</a>
              <Button size="sm" isLoading={isRunningDemo} onClick={handleRunDemo}>{isRunningDemo ? 'Running demo…' : 'Run end-to-end demo'}</Button>
            </div>
          </div>
          {demoError && <p role="alert" className="mt-3 text-xs text-[#EF4444]">{demoError}</p>}
          {demoMessage && demoResult && (
            <p role="status" className="mt-3 text-xs text-[#A7A7A7]">
              {demoMessage} {demoResult.traffic.requests_generated} requests · {demoResult.traffic.successful_requests} successful · {demoResult.traffic.failed_requests} simulated failures · {demoResult.evaluation.rules_evaluated} rules · {demoResult.evaluation.alerts_triggered} new alerts · {demoResult.evaluation.alerts_updated} updated.
            </p>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded space-y-1">
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Monitored Services</span>
          <div className="text-2xl font-bold font-mono text-[#F7F7F7]">{services.length}</div>
        </div>
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded space-y-1">
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Healthy Services</span>
          <div className="text-2xl font-bold font-mono text-[#10B981]">
            {services.filter((s) => s.status === 'healthy').length}
          </div>
        </div>
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded space-y-1 cursor-pointer" onClick={() => navigate('/app/alerts')}>
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Active Triggered Alerts</span>
          <div className="text-2xl font-bold font-mono text-[#F59E0B]">{activeAlerts.length}</div>
        </div>
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded space-y-1 cursor-pointer" onClick={() => navigate('/app/incidents')}>
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Open Operational Incidents</span>
          <div className="text-2xl font-bold font-mono text-[#EF4444]">{openIncidents.length}</div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono font-semibold uppercase text-[#F7F7F7]">Services Overview</h2>
          <button onClick={() => navigate('/app/services')} className="text-xs font-mono text-[#E50039] hover:underline">
            Manage Services →
          </button>
        </div>
        {services.length === 0 ? (
          <EmptyState title="No Monitored Services" description="No services registered yet." actionLabel="Register Service" onAction={() => navigate('/app/services')} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Service</TableHead>
                <TableHead>Env</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Seen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {services.slice(0, 5).map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-semibold">{s.name}</TableCell>
                  <TableCell>{s.environment}</TableCell>
                  <TableCell><StatusIndicator status={s.status} /></TableCell>
                  <TableCell>{formatDate(s.last_seen_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="space-y-3">
        <h2 className="text-xs font-mono font-semibold uppercase text-[#F7F7F7]">Recent Events Log</h2>
        {events.length === 0 ? (
          <EmptyState title="No Events Recorded" description="No HTTP telemetry events recorded yet." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Method</TableHead>
                <TableHead>Endpoint</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Duration</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id}>
                  <TableCell>{formatDate(e.occurred_at)}</TableCell>
                  <TableCell className="text-[#E50039] font-bold">{e.method || 'N/A'}</TableCell>
                  <TableCell>{e.endpoint || 'N/A'}</TableCell>
                  <TableCell>{e.status_code || 'N/A'}</TableCell>
                  <TableCell>{formatDuration(e.duration_ms)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
};
