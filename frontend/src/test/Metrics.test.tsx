import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Metrics } from '../pages/Metrics';
import { getTelemetryMetricsApi } from '../services/telemetry';

vi.mock('../services/telemetry', () => ({ getTelemetryMetricsApi: vi.fn() }));

const data = [
  { id: 1, service_id: 'service-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', metric_name: 'avg_latency_ms', value: 44, window_seconds: 60, recorded_at: '2026-10-16T11:45:00Z' },
  { id: 2, service_id: 'service-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', metric_name: 'avg_latency_ms', value: 62, window_seconds: 60, recorded_at: '2026-10-16T11:55:00Z' },
  { id: 3, service_id: 'other-service', metric_name: 'error_rate', value: 0.12, window_seconds: 300, recorded_at: '2026-10-16T11:50:00Z' },
  { id: 4, service_id: 'other-service', metric_name: 'error_rate', value: 0.3, window_seconds: 300, recorded_at: '2026-10-10T11:50:00Z' },
] as never[];

describe('Metrics page', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-16T12:00:00Z'));
    vi.mocked(getTelemetryMetricsApi).mockResolvedValue(data);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const width = this.dataset.testid === 'metric-chart-container' ? 280 : 0;
      return { x: 0, y: 0, top: 0, left: 0, right: width, bottom: 248, width, height: 248, toJSON: () => ({}) } as DOMRect;
    });
  });

  afterEach(() => vi.restoreAllMocks());

  it('keeps metric selector, chart, record count, and table on the same filtered series', async () => {
    render(<MemoryRouter><Metrics /></MemoryRouter>);
    expect(await screen.findByText('Metric records')).toBeInTheDocument();
    expect(screen.getByText('Records:').parentElement).toHaveTextContent('2');
    expect(screen.getByText('44')).toBeInTheDocument();
    expect(screen.getByText('62')).toBeInTheDocument();
    expect(screen.queryByText('0.12')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('metric-chart-container').querySelector('svg')).toHaveAttribute('viewBox', '0 0 280 248'));

    fireEvent.change(screen.getByLabelText('Select metric'), { target: { value: 'error_rate' } });
    await waitFor(() => expect(screen.getByText('0.12')).toBeInTheDocument());
    expect(screen.queryByText('44')).not.toBeInTheDocument();
    expect(screen.getByText('Records:').parentElement).toHaveTextContent('1');

    fireEvent.change(screen.getByLabelText('Filter metrics by name'), { target: { value: 'latency' } });
    await waitFor(() => expect(screen.getByText('44')).toBeInTheDocument());
    expect(screen.queryByText('0.12')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Scrollable metric records table')).toHaveClass('overflow-x-auto');
    expect(screen.getByLabelText('Scrollable metric records table').querySelector('table')).toHaveClass('min-w-[720px]');
  });

  it('filters stored records by selected time window and provides refresh', async () => {
    render(<MemoryRouter><Metrics /></MemoryRouter>);
    expect(await screen.findByText('44')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Select metric'), { target: { value: 'error_rate' } });
    fireEvent.change(screen.getByLabelText('Time range'), { target: { value: '168' } });
    await waitFor(() => expect(screen.getByText('Records:').parentElement).toHaveTextContent('2'));
    expect(screen.getByText('0.3')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Time range'), { target: { value: '24' } });
    await waitFor(() => expect(screen.getByText('Records:').parentElement).toHaveTextContent('1'));
    expect(screen.queryByText('0.3')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Refresh'));
    await waitFor(() => expect(getTelemetryMetricsApi).toHaveBeenCalledTimes(2));
  });
});
