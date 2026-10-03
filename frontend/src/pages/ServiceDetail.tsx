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

export const ServiceDetail: React.FC = () => {
  const { serviceId = '' } = useParams();
  const [service, setService] = useState<Service | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
    <PageHeader title={service.name} description={`${service.identifier || service.id} · ${service.environment}`} action={<Link to="/app/services" className="text-sm text-[#E50039]">← All services</Link>} />
    {service.repository_url && <a href={service.repository_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 border border-[#333333] bg-[#1F1F1F] px-3 py-2 text-xs text-[#F7F7F7] hover:border-[#E50039]">Source repository <span className="font-mono text-[#E50039]">{service.repository_url.replace('https://github.com/', '')} ↗</span></a>}
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
  </div>;
};
