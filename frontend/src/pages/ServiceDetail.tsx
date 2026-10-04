import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PageHeader } from '../components/layout/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';
import { ErrorState } from '../components/ui/ErrorState';
import { getServiceByIdApi } from '../services/services';
import { getTelemetryEventsApi, getTelemetryLogsApi, getTelemetryMetricsApi } from '../services/telemetry';
import { fetchAlertsApi } from '../services/alerts';
import { fetchIncidentsApi } from '../services/incidents';
import { Alert, Incident, LogEntry, Metric, Service, TelemetryEvent } from '../types';
import { formatDate, formatDuration, safeExtractErrorMessage } from '../lib/utils';
import { useAuth } from '../app/AuthContext';
import { rotateServiceIngestKeyApi } from '../services/services';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';

export const ServiceDetail: React.FC = () => {
  const { serviceId = '' } = useParams();
  const { user } = useAuth();
  const isAdmin = user?.role.toLowerCase() === 'admin';
  const [service, setService] = useState<Service | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rotateConfirmOpen, setRotateConfirmOpen] = useState(false);
  const [rotatedKey, setRotatedKey] = useState<string | null>(null);
  const [rotateError, setRotateError] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState(false);
  const [keyCopied, setKeyCopied] = useState(false);

  const rotateKey = async () => {
    if (!service) return;
    setIsRotating(true); setRotateError(null);
    try {
      const result = await rotateServiceIngestKeyApi(service.id);
      setRotateConfirmOpen(false); setRotatedKey(result.ingest_key); setKeyCopied(false);
    } catch (err) { setRotateError(safeExtractErrorMessage(err)); }
    finally { setIsRotating(false); }
  };
  const powershellSignal = (serviceIdentifier: string) => {
    const safeIdentifier = serviceIdentifier.replace(/`/g, '``').replace(/"/g, '`"');
    return `$key = Read-Host "Paste the ingestion key for ${safeIdentifier}"
$body = @{
  service_id = "${safeIdentifier}"
  method = "GET"
  endpoint = "/health"
  status_code = 200
  duration_ms = 12
  outcome = "success"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "${window.location.origin}/api/v1/telemetry/events" -Headers @{ "X-Ingest-Key" = $key } -ContentType "application/json" -Body $body`;
  };

  const load = useCallback(async () => {
    if (!serviceId) return;
    setLoading(true); setError(null);
    try {
      const [svc, ev, met, log, alt, inc] = await Promise.all([
        getServiceByIdApi(serviceId), getTelemetryEventsApi({ service_id: serviceId, limit: 50 }),
        getTelemetryMetricsApi({ service_id: serviceId, limit: 200 }), getTelemetryLogsApi({ service_id: serviceId, limit: 30 }),
        fetchAlertsApi({ service_id: serviceId, limit: 50 }), fetchIncidentsApi({ service_id: serviceId, limit: 50 }),
      ]);
      setService(svc); setEvents(ev); setMetrics(met); setLogs(log); setAlerts(alt); setIncidents(inc);
    } catch (err) { setError(safeExtractErrorMessage(err)); }
    finally { setLoading(false); }
  }, [serviceId]);

  useEffect(() => { void load(); }, [load]);
  if (loading) return <div className="space-y-6"><PageHeader title="Service detail" description="Loading service telemetry and operational state." /><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !service) return <div className="space-y-6"><PageHeader title="Service detail" description="Service inventory and supporting telemetry." /><ErrorState message={error || 'Service not found.'} onRetry={load} /><Link to="/app/services" className="text-sm text-[#E50039]">Back to services</Link></div>;

  const errorCount = events.filter((event) => (event.status_code || 0) >= 400).length;
  const averageLatency = events.length ? events.reduce((sum, event) => sum + (event.duration_ms || 0), 0) / events.length : null;
  const activeAlerts = alerts.filter((alert) => alert.status === 'active').length;
  const activeIncidents = incidents.filter((incident) => incident.status !== 'resolved').length;
  return <div className="space-y-6">
    <PageHeader title={service.name} description={`${service.identifier || service.id} · ${service.environment}`} action={<div className="flex flex-wrap items-center gap-3">{isAdmin && <Button size="sm" variant="secondary" onClick={() => { setRotateError(null); setRotateConfirmOpen(true); }}>Rotate ingestion key</Button>}<Link to="/app/services" className="text-sm text-[#E50039]">← All services</Link></div>} />
    {service.repository_url && <a href={service.repository_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 border border-[#333333] bg-[#1F1F1F] px-3 py-2 text-xs text-[#F7F7F7] hover:border-[#E50039]">Linked GitHub repository <span className="font-mono text-[#E50039]">{service.repository_url.replace('https://github.com/', '')} ↗</span></a>}
    {service.repository_url && <p className="-mt-3 max-w-3xl text-xs text-[#A7A7A7]">This repository link stores source metadata; it does not install monitoring code. To connect runtime telemetry, add NexPulse reporting to that app’s server-side code using identifier <code className="text-[#F7F7F7]">{service.identifier}</code>. GitHub-hosted runners cannot send to a localhost NexPulse address; use a publicly reachable NexPulse API URL after deployment.</p>}
    <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {[
        ['Health', <Badge variant={service.status === 'healthy' ? 'healthy' : service.status === 'degraded' ? 'warning' : 'critical'}>{service.status}</Badge>],
        ['Last seen', service.last_seen_at ? formatDate(service.last_seen_at) : 'No signal'],
        ['Recent requests', events.length], ['Observed errors', errorCount],
        ['Mean latency', averageLatency === null ? '—' : formatDuration(averageLatency)], ['Active alerts / incidents', `${activeAlerts} / ${activeIncidents}`],
      ].map(([label, value]) => <div key={String(label)} className="rounded border border-[#333333] bg-[#1F1F1F] p-4"><p className="text-[10px] font-mono uppercase text-[#A7A7A7]">{label}</p><div className="mt-2 text-sm font-semibold">{value}</div></div>)}
    </section>
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <section className="rounded border border-[#333333] bg-[#1F1F1F] p-4"><h2 className="mb-3 font-mono text-sm font-semibold uppercase">Recent request signals</h2>
        {events.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-[#A7A7A7]"><tr><th className="py-2">Time</th><th>Route</th><th>Status</th><th>Latency</th></tr></thead><tbody className="divide-y divide-[#333333]">{events.slice(0, 12).map((event) => <tr key={event.id}><td className="py-2 pr-3">{formatDate(event.occurred_at)}</td><td className="max-w-[220px] truncate pr-3 font-mono">{event.method} {event.endpoint}</td><td className={(event.status_code || 0) >= 400 ? 'text-[#EF4444]' : 'text-[#10B981]'}>{event.status_code}</td><td>{formatDuration(event.duration_ms)}</td></tr>)}</tbody></table></div> : <p className="text-sm text-[#A7A7A7]">No request signals recorded in this sample.</p>}
      </section>
      <section className="rounded border border-[#333333] bg-[#1F1F1F] p-4"><h2 className="mb-3 font-mono text-sm font-semibold uppercase">Latest metrics</h2>
        {metrics.length ? <div className="space-y-2">{metrics.slice(0, 12).map((metric) => <div key={metric.id} className="flex justify-between gap-4 border-b border-[#333333] py-2 text-xs"><span className="font-mono">{metric.metric_name}</span><span className="text-[#10B981]">{metric.value} <span className="text-[#777]">· {formatDate(metric.recorded_at)}</span></span></div>)}</div> : <p className="text-sm text-[#A7A7A7]">No metrics recorded for this service.</p>}
      </section>
      <section className="rounded border border-[#333333] bg-[#1F1F1F] p-4"><h2 className="mb-3 font-mono text-sm font-semibold uppercase">Recent logs</h2>
        {logs.length ? <div className="space-y-2">{logs.slice(0, 10).map((log) => <div key={log.id} className="border-b border-[#333333] py-2 text-xs"><span className="mr-2 font-mono text-[#A7A7A7]">{log.level}</span>{log.message}<span className="mt-1 block text-[10px] text-[#777]">{formatDate(log.occurred_at)}</span></div>)}</div> : <p className="text-sm text-[#A7A7A7]">No logs recorded for this service.</p>}
      </section>
      <section className="rounded border border-[#333333] bg-[#1F1F1F] p-4"><h2 className="mb-3 font-mono text-sm font-semibold uppercase">Open incidents & alert history</h2>
        {[...incidents.filter((incident) => incident.status !== 'resolved').map((item) => ({ id: item.id, title: item.title, kind: 'Incident', status: item.status })), ...alerts.map((item) => ({ id: item.id, title: item.rule_name || 'Triggered alert', kind: 'Alert', status: item.status }))].length ? <div className="space-y-2">{incidents.filter((incident) => incident.status !== 'resolved').slice(0, 6).map((incident) => <Link key={incident.id} to={`/app/incidents/${incident.id}`} className="flex justify-between gap-3 border-b border-[#333333] py-2 text-xs hover:text-[#E50039]"><span>{incident.title}</span><span>{incident.status}</span></Link>)}{alerts.slice(0, 6).map((alert) => <div key={alert.id} className="flex justify-between gap-3 border-b border-[#333333] py-2 text-xs"><span>{alert.rule_name || 'Triggered alert'}</span><span>{alert.status}</span></div>)}</div> : <p className="text-sm text-[#A7A7A7]">No alerts or active incidents for this service.</p>}
      </section>
    </div>
    <Modal isOpen={rotateConfirmOpen} onClose={() => { if (!isRotating) setRotateConfirmOpen(false); }} title="Rotate ingestion key">
      <div className="space-y-4">
        <p className="text-sm">Create a replacement key for <strong>{service.name}</strong>?</p>
        <p className="text-sm text-[#F59E0B]">The current key stops working immediately. Update the secret in this service’s runtime or GitHub Actions before sending more telemetry. The new key is shown once.</p>
        {rotateError && <p role="alert" className="text-sm text-[#EF4444]">{rotateError}</p>}
        <div className="flex justify-end gap-2"><Button variant="secondary" disabled={isRotating} onClick={() => setRotateConfirmOpen(false)}>Cancel</Button><Button isLoading={isRotating} onClick={() => void rotateKey()}>Rotate key now</Button></div>
      </div>
    </Modal>
    <Modal isOpen={!!rotatedKey} onClose={() => setRotatedKey(null)} title="New ingestion key" className="max-w-xl">
      <div className="space-y-4">
        <p className="border border-[#10B981]/30 bg-[#10B981]/10 p-3 text-sm text-[#10B981]">Copy and save this key now. NexPulse cannot show it again.</p>
        <div className="flex gap-2"><div className="min-w-0 flex-1 break-all border border-[#333333] bg-[#262626] p-3 font-mono text-xs text-[#E50039]">{rotatedKey}</div><Button variant="secondary" size="sm" onClick={() => { if (rotatedKey) void navigator.clipboard.writeText(rotatedKey).then(() => setKeyCopied(true)).catch(() => setRotateError('Clipboard access failed. Select and copy the key manually.')); }}>{keyCopied ? 'Copied' : 'Copy key'}</Button></div>
        <p className="text-xs text-[#A7A7A7]">This key belongs only to service identifier <code>{service.identifier}</code>. Use it with that exact identifier.</p>
        <div><p className="mb-2 text-xs font-mono uppercase text-[#A7A7A7]">PowerShell local smoke signal</p><pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all border border-[#333333] bg-[#191919] p-3 text-xs text-[#F7F7F7]">{powershellSignal(service.identifier || service.id)}</pre><Button variant="secondary" size="sm" onClick={() => { void navigator.clipboard.writeText(powershellSignal(service.identifier || service.id)).then(() => setKeyCopied(true)).catch(() => setRotateError('Clipboard access failed. Select and copy the command manually.')); }}>Copy PowerShell command</Button></div>
        <p className="text-xs text-[#A7A7A7]">Run this from PowerShell on the same computer as the local app. At the prompt, paste the key shown above; don’t put the key in the Read-Host prompt text.</p>
        <Button className="w-full" onClick={() => setRotatedKey(null)}>Done</Button>
      </div>
    </Modal>
  </div>;
};
