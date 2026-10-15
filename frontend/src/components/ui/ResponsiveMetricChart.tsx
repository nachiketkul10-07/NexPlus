import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Metric } from '../../types';
import { formatDate } from '../../lib/utils';

interface ResponsiveMetricChartProps {
  series: Metric[];
  metricName: string;
}

const HEIGHT = 248;
const MARGIN = { top: 16, right: 12, bottom: 42, left: 58 };
const formatValue = (value: number) => Number.isInteger(value) ? String(value) : Number(value.toFixed(2)).toString();

export const ResponsiveMetricChart: React.FC<ResponsiveMetricChartProps> = ({ series, metricName }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const updateWidth = () => setWidth(Math.floor(container.getBoundingClientRect().width));
    updateWidth();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateWidth);
      return () => window.removeEventListener('resize', updateWidth);
    }
    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => setActiveIndex(null), [series, metricName]);

  const chart = useMemo(() => {
    const plotWidth = Math.max(1, width - MARGIN.left - MARGIN.right);
    const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
    const values = series.map((point) => point.value);
    const rawMin = Math.min(0, ...values);
    const rawMax = Math.max(0, ...values);
    const span = rawMax - rawMin || 1;
    const min = rawMin >= 0 ? 0 : rawMin - span * 0.08;
    const max = rawMax <= 0 ? 0 : rawMax + span * 0.08;
    const y = (value: number) => MARGIN.top + (max - value) / (max - min) * plotHeight;
    const x = (index: number) => MARGIN.left + (series.length < 2 ? plotWidth / 2 : index / (series.length - 1) * plotWidth);
    const yTicks = Array.from({ length: 4 }, (_, index) => max - index * (max - min) / 3);
    const tickCount = width < 380 ? 2 : width < 600 ? 3 : width < 1000 ? 4 : 6;
    const xTickIndexes = Array.from(new Set(Array.from({ length: Math.min(tickCount, series.length) }, (_, index) =>
      Math.round(index * (series.length - 1) / Math.max(1, Math.min(tickCount, series.length) - 1)),
    )));
    const path = series.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`).join(' ');
    return { plotWidth, plotHeight, min, max, y, x, yTicks, xTickIndexes, path };
  }, [series, width]);

  const active = activeIndex === null ? null : series[activeIndex] ?? null;
  const hasWidth = width > 0;

  return <div className="min-w-0 w-full">
    <div ref={containerRef} className="h-64 min-w-0 w-full sm:h-72" data-testid="metric-chart-container">
      {hasWidth && series.length > 0 ? <svg
        viewBox={`0 0 ${width} ${HEIGHT}`}
        className="block h-full w-full overflow-hidden"
        role="img"
        aria-labelledby="metric-chart-title metric-chart-description"
        preserveAspectRatio="none"
      >
        <title id="metric-chart-title">{metricName} trend</title>
        <desc id="metric-chart-description">{series.length} persisted samples in chronological order. Select or focus a point to inspect its value and timestamp.</desc>
        {chart.yTicks.map((tick, index) => {
          const y = chart.y(tick);
          return <g key={`y-${index}`}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y} y2={y} stroke="#333333" strokeWidth="1" />
            <text x={MARGIN.left - 8} y={y + 3.5} textAnchor="end" fill="#A7A7A7" fontSize="10" fontFamily="monospace">{formatValue(tick)}</text>
          </g>;
        })}
        <line x1={MARGIN.left} x2={MARGIN.left} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} stroke="#555555" strokeWidth="1" />
        <line x1={MARGIN.left} x2={width - MARGIN.right} y1={HEIGHT - MARGIN.bottom} y2={HEIGHT - MARGIN.bottom} stroke="#555555" strokeWidth="1" />
        {chart.path && <path d={chart.path} fill="none" stroke="#E50039" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
        {chart.xTickIndexes.map((index) => {
          const timestamp = new Date(series[index].recorded_at);
          const label = Number.isNaN(timestamp.getTime())
            ? 'Unknown time'
            : timestamp.toLocaleString([], width < 380
              ? { hour: '2-digit', minute: '2-digit' }
              : { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
          return <g key={`x-${index}`}>
            <line x1={chart.x(index)} x2={chart.x(index)} y1={HEIGHT - MARGIN.bottom} y2={HEIGHT - MARGIN.bottom + 4} stroke="#777777" />
            <text x={chart.x(index)} y={HEIGHT - 15} textAnchor={index === 0 ? 'start' : index === series.length - 1 ? 'end' : 'middle'} fill="#A7A7A7" fontSize="9" fontFamily="monospace">{label}</text>
          </g>;
        })}
        {series.map((point, index) => <circle
          key={point.id}
          cx={chart.x(index)} cy={chart.y(point.value)} r={activeIndex === index ? 5 : 3}
          fill={activeIndex === index ? '#F7F7F7' : '#E50039'} stroke="#191919" strokeWidth="1.5"
          tabIndex={0} role="button"
          aria-label={`${metricName}: ${formatValue(point.value)}, ${formatDate(point.recorded_at)}`}
          onMouseEnter={() => setActiveIndex(index)} onFocus={() => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)} onBlur={() => setActiveIndex(null)}
        />)}
      </svg> : <div className="h-full w-full animate-pulse rounded bg-[#262626]" aria-label="Sizing metric chart" />}
    </div>
    <p className="mt-2 min-h-5 break-words text-xs text-[#A7A7A7]" aria-live="polite">
      {active ? <><span className="font-mono text-[#F7F7F7]">{formatValue(active.value)}</span> · {formatDate(active.recorded_at)}</> : `${series.length} persisted sample${series.length === 1 ? '' : 's'} · focus or point to inspect a value`}
    </p>
  </div>;
};
