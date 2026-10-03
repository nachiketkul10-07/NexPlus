import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { fetchIncidentsApi } from '../services/incidents';
import { Incident } from '../types';
import { AIAnalysisPanel } from '../components/ui/AIAnalysisPanel';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { NexPulseLogo } from '../components/ui/NexPulseLogo';
import { safeExtractErrorMessage } from '../lib/utils';

const countCard = (label: string, value: number, tone: string) => (
  <div className="rounded-xl border border-white/[0.08] bg-[#1E2025]/80 px-4 py-3">
    <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-white/45">{label}</div>
    <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
  </div>
);

export const AIAssistant: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchIncidentsApi({ limit: 50 });
      setIncidents(data);
      setSelectedIncidentId((current) => data.some((incident) => incident.id === current) ? current : data[0]?.id ?? '');
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIncidents();
  }, [loadIncidents]);

  const selectedIncident = useMemo(
    () => incidents.find((incident) => incident.id === selectedIncidentId),
    [incidents, selectedIncidentId],
  );
  const activeCount = incidents.filter((incident) => incident.status !== 'resolved').length;
  const criticalCount = incidents.filter((incident) => incident.severity === 'critical' && incident.status !== 'resolved').length;

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl border border-white/[0.09] bg-[radial-gradient(ellipse_at_85%_0%,rgba(229,0,57,0.19),transparent_42%),linear-gradient(135deg,#222329,#191A1F_64%)] p-5 sm:p-7">
        <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full border border-[#E50039]/10" />
        <div className="pointer-events-none absolute -right-7 -top-11 h-44 w-44 rounded-full border border-[#E50039]/10" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-[#E50039]/25 bg-[#E50039]/[0.08] shadow-[0_0_32px_rgba(229,0,57,0.13)]">
              <NexPulseLogo variant="mark" className="[&>svg]:h-10 [&>svg]:w-10" />
            </div>
            <div>
              <div className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-[#FF6A8B]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#E50039] shadow-[0_0_10px_#E50039]" /> Incident intelligence
              </div>
              <h1 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">NexPulse AI Assistant</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-white/60">
                Turn incident telemetry into evidence-backed hypotheses and practical diagnostic steps. Every result is advisory and reviewable.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:min-w-[330px]">
            {countCard('Incidents', incidents.length, 'text-white')}
            {countCard('Open', activeCount, 'text-emerald-400')}
            {countCard('Critical', criticalCount, criticalCount ? 'text-rose-400' : 'text-white/65')}
          </div>
        </div>
      </section>

      {isLoading ? (
        <div className="space-y-4 rounded-xl border border-white/[0.08] bg-[#1E2025] p-5">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : error ? (
        <div className="flex flex-col gap-4 rounded-xl border border-rose-500/30 bg-rose-500/[0.07] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-rose-200">Couldn’t load the incident stream</h2>
            <p className="mt-1 text-xs text-rose-100/65">{error}</p>
          </div>
          <button onClick={loadIncidents} className="rounded-lg border border-rose-300/20 bg-rose-400/10 px-4 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-400/20">
            Retry connection
          </button>
        </div>
      ) : incidents.length === 0 ? (
        <EmptyState
          title="No incidents to analyze yet"
          description="The assistant needs an incident with telemetry evidence. Generate demo traffic or wait for an alert rule to open an incident, then refresh this view."
          actionLabel="Refresh incident stream"
          onAction={loadIncidents}
          className="min-h-64 rounded-2xl border-white/[0.08] bg-[#1E2025]"
        />
      ) : (
        <>
          <section className="rounded-xl border border-white/[0.08] bg-[#1E2025] p-4 sm:p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0 flex-1">
                <label htmlFor="ai-incident-select" className="mb-2 block text-[10px] font-mono uppercase tracking-[0.16em] text-white/45">
                  Incident under investigation
                </label>
                <select
                  id="ai-incident-select"
                  value={selectedIncidentId}
                  onChange={(event) => setSelectedIncidentId(event.target.value)}
                  className="h-11 w-full rounded-lg border border-white/10 bg-[#17181D] px-3 text-sm text-white outline-none transition focus:border-[#E50039]/60 focus:ring-2 focus:ring-[#E50039]/15 xl:max-w-3xl"
                >
                  {incidents.map((incident) => (
                    <option key={incident.id} value={incident.id}>
                      [{incident.severity.toUpperCase()}] {incident.title} · {incident.status.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-white/45">
                <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_9px_rgba(52,211,153,0.6)]" />
                Secure server-side analysis
              </div>
            </div>
            {selectedIncident && (
              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/[0.07] pt-4 text-xs text-white/55">
                <span><span className="text-white/35">SERVICE</span> <span className="ml-1.5 text-white/80">{selectedIncident.service_name || 'Monitored service'}</span></span>
                <span><span className="text-white/35">DETECTED</span> <span className="ml-1.5 text-white/80">{new Date(selectedIncident.detected_at).toLocaleString()}</span></span>
                {selectedIncident.originating_alert_rule_name && <span><span className="text-white/35">TRIGGER</span> <span className="ml-1.5 text-white/80">{selectedIncident.originating_alert_rule_name}</span></span>}
                <span className={`rounded-full px-2 py-1 text-[10px] font-mono uppercase ${selectedIncident.severity === 'critical' ? 'bg-rose-500/10 text-rose-300' : selectedIncident.severity === 'warning' ? 'bg-amber-500/10 text-amber-300' : 'bg-sky-500/10 text-sky-300'}`}>
                  {selectedIncident.severity} severity
                </span>
              </div>
            )}
          </section>

          {selectedIncidentId && <AIAnalysisPanel incidentId={selectedIncidentId} key={selectedIncidentId} />}
        </>
      )}
    </div>
  );
};
