import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { getTelemetryMetricsApi } from '../services/telemetry';
import { Metric } from '../types';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { Input } from '../components/ui/Input';
import { formatDate, safeExtractErrorMessage } from '../lib/utils';
import { ResponsiveMetricChart } from '../components/ui/ResponsiveMetricChart';
import { Button } from '../components/ui/Button';

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

  useEffect(() => { void fetchMetrics(); }, [fetchMetrics]);

  const cutoff = Date.now() - rangeHours * 60 * 60 * 1000;
  const filtered = metrics.filter((metric) =>
    metric.metric_name.toLowerCase().includes(search.trim().toLowerCase())
    && new Date(metric.recorded_at).getTime() >= cutoff,
  );
  const metricNames = Array.from(new Set(filtered.map((metric) => metric.metric_name))).sort();
  const chartMetric = metricNames.includes(selectedMetric) ? selectedMetric : metricNames[0] || '';
  const visibleMetrics = chartMetric ? filtered.filter((metric) => metric.metric_name === chartMetric) : [];
  const series = visibleMetrics.slice().sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()).slice(-48);

  return <div className="min-w-0 space-y-5 sm:space-y-6">
    <PageHeader
      title="Telemetry Metrics"
      description="Persisted request, latency, error, and health measurements from monitored services."
      action={<Button variant="secondary" size="sm" onClick={() => void fetchMetrics()} isLoading={isLoading}>Refresh</Button>}
    />

    <section aria-label="Metric filters" className="grid min-w-0 grid-cols-1 gap-3 rounded border border-[#333333] bg-[#1F1F1F] p-3 sm:grid-cols-2 sm:p-4 lg:grid-cols-[minmax(12rem,1fr)_minmax(10rem,14rem)_auto] lg:items-end">
      <div className="min-w-0">
        <label htmlFor="metric-search" className="mb-1.5 block text-xs font-mono text-[#A7A7A7]">Search metrics</label>
        <Input id="metric-search" aria-label="Filter metrics by name" placeholder="Filter by metric name..." value={search} onChange={(event) => setSearch(event.target.value)} className="w-full min-w-0 max-w-none" />
      </div>
      <div className="min-w-0">
        <label htmlFor="metric-window" className="mb-1.5 block text-xs font-mono text-[#A7A7A7]">Time window</label>
        <select id="metric-window" aria-label="Time range" value={rangeHours} onChange={(event) => setRangeHours(Number(event.target.value))} className="h-10 w-full min-w-0 rounded border border-[#333333] bg-[#191919] px-3 text-sm text-[#F7F7F7] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E50039]">
          <option value={1}>Last hour</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option>
        </select>
      </div>
      <p className="min-w-0 self-center text-xs font-mono text-[#A7A7A7]" aria-live="polite">Records: <span className="text-[#F7F7F7]">{visibleMetrics.length}</span>{series.length < visibleMetrics.length ? ` · chart shows latest ${series.length}` : ''}</p>
    </section>

    {isLoading ? <Skeleton className="h-64 w-full" /> : error ? <ErrorState message={error} onRetry={() => void fetchMetrics()} /> : filtered.length === 0 ? (
      <EmptyState title={search.trim() ? 'No Matching Metrics' : 'No Metrics Recorded'} description={search.trim() ? 'Try another metric name or expand the time window.' : 'No metric snapshots have been ingested in this time window.'} />
    ) : <>
      <section className="min-w-0 rounded border border-[#333333] bg-[#1F1F1F] p-3 sm:p-5" aria-label={`${chartMetric} trend`}>
        <div className="mb-3 grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(11rem,15rem)] sm:items-end">
          <div className="min-w-0">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#A7A7A7]">Persisted trend</p>
            <h2 className="mt-1 break-words font-mono text-base text-[#F7F7F7] sm:text-lg" title={chartMetric}>{chartMetric}</h2>
          </div>
          <div className="min-w-0">
            <label htmlFor="metric-select" className="mb-1.5 block text-xs font-mono text-[#A7A7A7]">Metric series</label>
            <select id="metric-select" aria-label="Select metric" value={chartMetric} onChange={(event) => setSelectedMetric(event.target.value)} className="h-10 w-full min-w-0 rounded border border-[#333333] bg-[#191919] px-3 text-sm text-[#F7F7F7] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#E50039]">
              {metricNames.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </div>
        </div>
        <ResponsiveMetricChart series={series} metricName={chartMetric} />
      </section>

      <section aria-label="Metric records" className="min-w-0 space-y-2">
        <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-[#F7F7F7]">Metric records</h2>
          <p className="min-w-0 break-words text-xs text-[#A7A7A7]">Showing the selected metric within the chosen time window.</p>
        </div>
        <p className="text-[11px] text-[#777] md:hidden">Swipe horizontally to view timestamp, window, and full service ID.</p>
        <div className="w-full min-w-0 overflow-x-auto overscroll-x-contain rounded border border-[#333333] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E50039]" role="region" aria-label="Scrollable metric records table" tabIndex={0}>
          <table className="w-full min-w-[720px] table-fixed text-left text-sm text-[#F7F7F7]">
            <TableHeader><TableRow><TableHead className="w-[19%]">Timestamp</TableHead><TableHead className="w-[27%]">Metric</TableHead><TableHead className="w-[13%]">Value</TableHead><TableHead className="w-[12%]">Window</TableHead><TableHead className="w-[29%]">Service ID</TableHead></TableRow></TableHeader>
            <TableBody>{visibleMetrics.map((metric) => <TableRow key={metric.id}>
              <TableCell className="whitespace-nowrap">{formatDate(metric.recorded_at)}</TableCell>
              <TableCell className="break-words font-semibold text-[#F7F7F7]" title={metric.metric_name}>{metric.metric_name}</TableCell>
              <TableCell className="break-words font-mono text-[#10B981]">{metric.value}</TableCell>
              <TableCell className="whitespace-nowrap">{metric.window_seconds}s</TableCell>
              <TableCell className="break-all text-[#A7A7A7]" title={metric.service_id}>{metric.service_id}</TableCell>
            </TableRow>)}</TableBody>
          </table>
        </div>
      </section>
    </>}
  </div>;
};
