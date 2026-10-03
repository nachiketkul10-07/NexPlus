import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { getTelemetryLogsApi } from '../services/telemetry';
import { LogEntry } from '../types';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { formatDate, safeExtractErrorMessage } from '../lib/utils';

export const Logs: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [search, setSearch] = useState<string>('');
  const [levelFilter, setLevelFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getTelemetryLogsApi({ limit: 50, level: levelFilter || undefined });
      setLogs(data);
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [levelFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const filtered = logs.filter((l) =>
    l.message.toLowerCase().includes(search.toLowerCase())
  );

  const getBadgeVariant = (level: string) => {
    switch (level) {
      case 'DEBUG': return 'neutral';
      case 'INFO': return 'info';
      case 'WARN': return 'warning';
      case 'ERROR':
      case 'CRITICAL':
      case 'FATAL': return 'critical';
      default: return 'neutral';
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Application Logs"
        description="Structured application log streams ingested from monitored services."
      />

      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3 w-full sm:w-auto">
          <Input
            placeholder="Search log messages..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-md"
          />
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            className="h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-sm"
          >
            <option value="">All Severity Levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>
        <span className="text-xs font-mono text-[#A7A7A7]">Logs: {filtered.length}</span>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchLogs} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Logs Ingested"
          description="No application logs matching your filters have been ingested into NexPulse."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Timestamp</TableHead>
              <TableHead>Level</TableHead>
              <TableHead>Message</TableHead>
              <TableHead>Request ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((log) => (
              <TableRow key={log.id}>
                <TableCell>{formatDate(log.occurred_at)}</TableCell>
                <TableCell>
                  <Badge variant={getBadgeVariant(log.level)}>{log.level}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs text-[#F7F7F7]">{log.message}</TableCell>
                <TableCell className="text-[#A7A7A7]">{log.request_id || 'N/A'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
};
