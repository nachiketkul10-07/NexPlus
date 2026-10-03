import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { getTelemetryMetricsApi } from '../services/telemetry';
import { Metric } from '../types';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { Input } from '../components/ui/Input';
import { formatDate, safeExtractErrorMessage } from '../lib/utils';

export const Metrics: React.FC = () => {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [search, setSearch] = useState('');
  const [selectedMetric, setSelectedMetric] = useState('avg_latency_ms');
  const [rangeHours, setRangeHours] = useState(24);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try { setMetrics(await getTelemetryMetricsApi({ limit: 1000 })); }
    catch (err) { setError(safeExtractErrorMessage(err)); }
    finally { setIsLoading(false); }
  }, []);

  useEffect(() => { fetchMetrics(); }, [fetchMetrics]);

  const cutoff = Date.now() - rangeHours * 60 * 60 * 1000;
  const filtered = metrics.filter((m) => m.metric_name.toLowerCase().includes(search.toLowerCase()) && new Date(m.recorded_at).getTime() >= cutoff);
  const metricNames = Array.from(new Set(metrics.map((metric) => metric.metric_name))).sort();
  const chartMetric = metricNames.includes(selectedMetric) ? selectedMetric : metricNames[0] || selectedMetric;
  const series = filtered.filter((m) => m.metric_name === chartMetric).slice().reverse().slice(-48);
  const max = Math.max(1, ...series.map((m) => m.value));
  const points = series.map((m, i) => `${series.length < 2 ? 50 : i / (series.length - 1) * 100},${90 - m.value / max * 75}`).join(' ');

  return <div className="space-y-6">
    <PageHeader title="Telemetry Metrics" description="Persisted request, latency, error, and health measurements from monitored services." />
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <Input aria-label="Filter metrics by name" placeholder="Filter metrics by name..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-md" />
      <div className="flex items-center justify-between gap-4">
        <label className="text-xs font-mono text-[#A7A7A7]">Window
          <select aria-label="Time range" value={rangeHours} onChange={(e) => setRangeHours(Number(e.target.value))} className="ml-2 h-9 px-2 bg-[#1F1F1F] border border-[#333333] text-[#F7F7F7] rounded">
            <option value={1}>1 hour</option><option value={24}>24 hours</option><option value={168}>7 days</option>
          </select>
        </label>
        <span className="text-xs font-mono text-[#A7A7A7]">Records: {filtered.length}</span>
      </div>
    </div>
    {isLoading ? <Skeleton className="h-64 w-full" /> : error ? <ErrorState message={error} onRetry={fetchMetrics} /> : filtered.length === 0 ? <EmptyState title="No Metrics Recorded" description="No metric snapshots have been ingested in this time window." /> : <>
      <section className="rounded border border-[#333333] bg-[#1F1F1F] p-4 sm:p-6" aria-label={`${chartMetric} trend`}>
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] font-mono uppercase tracking-widest text-[#A7A7A7]">Persisted trend</p><h2 className="mt-1 font-mono text-lg text-[#F7F7F7]">{chartMetric}</h2></div><div className="flex items-center gap-3"><label className="text-xs font-mono text-[#A7A7A7]">Metric<select aria-label="Select metric" value={chartMetric} onChange={(e) => setSelectedMetric(e.target.value)} className="ml-2 h-9 bg-[#191919] border border-[#333333] px-2 text-[#F7F7F7] rounded">{metricNames.map((name) => <option key={name} value={name}>{name}</option>)}</select></label><span className="text-xs font-mono text-[#A7A7A7]">{series.length} samples</span></div></div>
        <svg viewBox="0 0 100 100" className="h-44 w-full overflow-visible" role="img" aria-label={`Trend of ${chartMetric}`} preserveAspectRatio="none">
          <path d="M0 90H100M0 52H100M0 15H100" stroke="#333333" strokeWidth=".6" />
          {series.length > 1 && <polyline points={points} fill="none" stroke="#E50039" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />}
        </svg>
        {series.length < 2 && <p className="text-xs text-[#A7A7A7]">More persisted samples are needed to draw a trend.</p>}
      </section>
      <Table><TableHeader><TableRow><TableHead>Timestamp</TableHead><TableHead>Metric</TableHead><TableHead>Value</TableHead><TableHead>Window</TableHead><TableHead>Service ID</TableHead></TableRow></TableHeader>
        <TableBody>{filtered.map((m) => <TableRow key={m.id}><TableCell>{formatDate(m.recorded_at)}</TableCell><TableCell className="font-semibold text-[#F7F7F7]">{m.metric_name}</TableCell><TableCell className="font-mono text-[#10B981]">{m.value}</TableCell><TableCell>{m.window_seconds}s</TableCell><TableCell className="text-[#A7A7A7]">{m.service_id}</TableCell></TableRow>)}</TableBody>
      </Table>
    </>}
  </div>;
};
