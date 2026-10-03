import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Skeleton } from '../components/ui/Skeleton';
import { ErrorState } from '../components/ui/ErrorState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { getServicesApi } from '../services/services';
import { fetchIncidentsApi } from '../services/incidents';
import { fetchAlertsApi } from '../services/alerts';
import { getTelemetryEventsApi } from '../services/telemetry';
import { Service, Incident, Alert, TelemetryEvent } from '../types';
import { safeExtractErrorMessage } from '../lib/utils';

export const Reports: React.FC = () => {
  const [services, setServices] = useState<Service[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReportData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [s, inc, alt, ev] = await Promise.all([
        getServicesApi(),
        fetchIncidentsApi({ limit: 100 }),
        fetchAlertsApi({ limit: 100 }),
        getTelemetryEventsApi({ limit: 500 }),
      ]);
      setServices(s);
      setIncidents(inc);
      setAlerts(alt);
      setEvents(ev);
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReportData();
  }, [fetchReportData]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Operational Reports" description="System telemetry and incident operational breakdown." />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="Operational Reports" description="System telemetry and incident operational breakdown." />
        <ErrorState message={error} onRetry={fetchReportData} />
      </div>
    );
  }

  const totalEvents = events.length;
  const errorEvents = events.filter((e) => (e.status_code || 0) >= 400).length;
  const observedErrorRate = totalEvents > 0 ? ((errorEvents / totalEvents) * 100).toFixed(2) : '0.00';

  const openIncidents = incidents.filter((i) => i.status !== 'resolved').length;
  const resolvedIncidents = incidents.filter((i) => i.status === 'resolved').length;
  const activeAlerts = alerts.filter((a) => a.status === 'active').length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operational Reliability Summary"
        description="Calculated metrics derived from persisted telemetry events, active alerts, and incident histories."
      />

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded">
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Observed Events</span>
          <div className="text-2xl font-bold font-mono text-[#F7F7F7]">{totalEvents}</div>
        </div>
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded">
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Telemetry Failure Rate</span>
          <div className="text-2xl font-bold font-mono text-[#E50039]">{totalEvents ? `${observedErrorRate}%` : '—'}</div>
        </div>
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded">
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Active Alerts</span>
          <div className="text-2xl font-bold font-mono text-[#F59E0B]">{activeAlerts}</div>
        </div>
        <div className="bg-[#1F1F1F] border border-[#333333] p-4 rounded">
          <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">Open / Resolved Incidents</span>
          <div className="text-2xl font-bold font-mono text-[#10B981]">
            {openIncidents} / {resolvedIncidents}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="text-xs font-mono font-semibold uppercase text-[#F7F7F7]">Service Telemetry Breakdown</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Service Name</TableHead>
              <TableHead>Environment</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Sampled Events</TableHead>
              <TableHead>Observed Errors</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {services.map((svc) => {
              const svcEvents = events.filter((e) => e.service_id === svc.id);
              const svcErrors = svcEvents.filter((e) => (e.status_code || 0) >= 400).length;
              return (
                <TableRow key={svc.id}>
                  <TableCell className="font-semibold text-[#F7F7F7]">{svc.name}</TableCell>
                  <TableCell>{svc.environment}</TableCell>
                  <TableCell className="uppercase text-xs font-mono">{svc.status}</TableCell>
                  <TableCell className="font-mono">{svcEvents.length}</TableCell>
                  <TableCell className="font-mono text-[#E50039]">{svcErrors}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
