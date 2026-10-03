import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { AlertRule, Alert, Service, AlertSeverity, AlertEvaluationSummary } from '../types';
import {
  fetchAlertRulesApi,
  fetchAlertsApi,
  createAlertRuleApi,
  updateAlertRuleApi,
  deleteAlertRuleApi,
  triggerEvaluationApi,
} from '../services/alerts';
import { getServicesApi } from '../services/services';
import { safeExtractErrorMessage } from '../lib/utils';

export const Alerts: React.FC = () => {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'resolved'>('all');

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [evaluationSummary, setEvaluationSummary] = useState<AlertEvaluationSummary | null>(null);

  // Modal State for New Rule
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  // New Rule Form Data
  const [ruleName, setRuleName] = useState<string>('');
  const [metricName, setMetricName] = useState<string>('error_rate');
  const [operator, setOperator] = useState<string>('>');
  const [threshold, setThreshold] = useState<string>('0.10');
  const [severity, setSeverity] = useState<AlertSeverity>('warning');
  const [windowSeconds, setWindowSeconds] = useState<string>('60');
  const [cooldownSeconds, setCooldownSeconds] = useState<string>('300');
  const [targetServiceId, setTargetServiceId] = useState<string>('');

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [rulesData, alertsData, servicesData] = await Promise.all([
        fetchAlertRulesApi(),
        fetchAlertsApi(),
        getServicesApi(),
      ]);
      setRules(rulesData);
      setAlerts(alertsData);
      setServices(servicesData);
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleEvaluate = async () => {
    setIsEvaluating(true);
    try {
      const summary = await triggerEvaluationApi();
      setEvaluationSummary(summary);
      await loadData();
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleToggleRule = async (rule: AlertRule) => {
    try {
      await updateAlertRuleApi(rule.id, { enabled: !rule.enabled });
      await loadData();
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    if (!window.confirm('Are you sure you want to delete this alert rule?')) return;
    try {
      await deleteAlertRuleApi(ruleId);
      await loadData();
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    }
  };

  const handleCreateRuleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!ruleName.trim()) {
      setFormError('Rule name is required.');
      return;
    }

    const threshNum = parseFloat(threshold);
    if (isNaN(threshNum)) {
      setFormError('Threshold must be a valid number.');
      return;
    }

    setIsSubmitting(true);
    try {
      await createAlertRuleApi({
        name: ruleName.trim(),
        metric_name: metricName.trim(),
        operator,
        threshold: threshNum,
        window_seconds: parseInt(windowSeconds, 10) || 60,
        cooldown_seconds: parseInt(cooldownSeconds, 10) || 300,
        severity,
        create_incident: true,
        enabled: true,
        service_id: targetServiceId.trim() ? targetServiceId.trim() : null,
      });

      setIsModalOpen(false);
      setRuleName('');
      setThreshold('0.10');
      await loadData();
    } catch (err) {
      setFormError(safeExtractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (statusFilter === 'active') return a.status === 'active';
    if (statusFilter === 'resolved') return a.status === 'resolved';
    return true;
  });

  const getSeverityBadgeVariant = (sev: AlertSeverity): 'critical' | 'warning' | 'info' | 'neutral' => {
    switch (sev) {
      case 'critical':
        return 'critical';
      case 'warning':
        return 'warning';
      case 'info':
        return 'info';
      default:
        return 'neutral';
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alert Engine & Rule Configuration"
        description="Real-time metric evaluation, threshold trigger condition state machine, and deduplicated alert history."
        action={
          <div className="flex items-center space-x-3">
            <Button variant="secondary" onClick={handleEvaluate} isLoading={isEvaluating}>
              Evaluate Rules Now
            </Button>
            <Button variant="primary" onClick={() => setIsModalOpen(true)}>
              + Create Alert Rule
            </Button>
          </div>
        }
      />

      {/* Evaluation Feedback Summary */}
      {evaluationSummary && (
        <div className="p-4 bg-[#1F1F1F] border border-[#333333] rounded text-xs text-[#F7F7F7] flex items-center justify-between">
          <div>
            <span className="font-mono font-bold text-[#E50039]">EVALUATION PIPELINE EXECUTED</span> —{' '}
            <span className="text-[#A7A7A7]">
              Evaluated {evaluationSummary.rules_evaluated} rules. Triggered:{' '}
              {evaluationSummary.alerts_triggered} new alerts, Updated:{' '}
              {evaluationSummary.alerts_updated} active alerts, Resolved:{' '}
              {evaluationSummary.alerts_resolved} alerts.
            </span>
          </div>
          <button
            onClick={() => setEvaluationSummary(null)}
            className="text-[#A7A7A7] hover:text-[#F7F7F7] font-mono text-xs ml-4"
          >
            [DISMISS]
          </button>
        </div>
      )}

      {/* Global Error Banner */}
      {error && <ErrorState message={error} onRetry={loadData} />}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="space-y-6">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          {/* TRIGGERED ALERTS SECTION */}
          <div className="bg-[#1F1F1F] border border-[#333333] rounded p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-mono font-bold text-[#F7F7F7]">
                  TRIGGERED ALERTS ({filteredAlerts.length})
                </h2>
                <p className="text-xs text-[#A7A7A7]">
                  Active and historical alert state records evaluated against telemetry rules.
                </p>
              </div>

              {/* Status Filter Tabs */}
              <div className="flex items-center space-x-1 bg-[#191919] p-1 border border-[#333333] rounded">
                {(['all', 'active', 'resolved'] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-3 py-1 rounded text-xs font-mono font-medium transition-colors ${
                      statusFilter === st
                        ? 'bg-[#E50039] text-white'
                        : 'text-[#A7A7A7] hover:text-[#F7F7F7]'
                    }`}
                  >
                    {st.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {filteredAlerts.length === 0 ? (
              <EmptyState
                title="No Triggered Alerts"
                description={
                  statusFilter === 'active'
                    ? 'No active threshold violations currently detected across monitored services.'
                    : 'No alert history records found matching filter criteria.'
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-[#F7F7F7]">
                  <thead className="bg-[#191919] text-[#A7A7A7] font-mono uppercase text-[10px] border-b border-[#333333]">
                    <tr>
                      <th className="p-3">Status</th>
                      <th className="p-3">Severity</th>
                      <th className="p-3">Rule Name</th>
                      <th className="p-3">Service</th>
                      <th className="p-3">Observed / Threshold</th>
                      <th className="p-3">Triggered Time</th>
                      <th className="p-3">Last Seen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#333333]">
                    {filteredAlerts.map((alert) => (
                      <tr key={alert.id} className="hover:bg-[#2A2A2A] transition-colors">
                        <td className="p-3">
                          <Badge variant={alert.status === 'active' ? 'critical' : 'healthy'}>
                            {alert.status.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <Badge variant={getSeverityBadgeVariant(alert.severity)}>
                            {alert.severity.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="p-3 font-medium text-[#F7F7F7]">
                          {alert.rule_name || alert.rule_id}
                        </td>
                        <td className="p-3 font-mono text-[#A7A7A7]">
                          {alert.service_name || alert.service_id}
                        </td>
                        <td className="p-3 font-mono">
                          <span className="text-[#E50039] font-bold">
                            {alert.current_value !== null && alert.current_value !== undefined
                              ? alert.current_value.toFixed(3)
                              : 'N/A'}
                          </span>{' '}
                          / <span className="text-[#A7A7A7]">{alert.threshold_value}</span>
                        </td>
                        <td className="p-3 text-[#A7A7A7] font-mono">
                          {new Date(alert.triggered_at).toLocaleString()}
                        </td>
                        <td className="p-3 text-[#A7A7A7] font-mono">
                          {new Date(alert.last_seen_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {/* CONFIGURED ALERT RULES SECTION */}
          <div className="bg-[#1F1F1F] border border-[#333333] rounded p-6 space-y-4">
            <div>
              <h2 className="text-sm font-mono font-bold text-[#F7F7F7]">
                CONFIGURED ALERT RULES ({rules.length})
              </h2>
              <p className="text-xs text-[#A7A7A7]">
                Active metric threshold logic, target evaluation windows, and deduplication cooldown parameters.
              </p>
            </div>

            {rules.length === 0 ? (
              <EmptyState
                title="No Alert Rules Configured"
                description="Create your first alert evaluation rule to monitor telemetry metric thresholds."
                actionLabel="Create Rule"
                onAction={() => setIsModalOpen(true)}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-[#F7F7F7]">
                  <thead className="bg-[#191919] text-[#A7A7A7] font-mono uppercase text-[10px] border-b border-[#333333]">
                    <tr>
                      <th className="p-3">State</th>
                      <th className="p-3">Rule Name</th>
                      <th className="p-3">Target Service</th>
                      <th className="p-3">Metric Name</th>
                      <th className="p-3">Condition</th>
                      <th className="p-3">Window / Cooldown</th>
                      <th className="p-3">Severity</th>
                      <th className="p-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#333333]">
                    {rules.map((rule) => (
                      <tr key={rule.id} className="hover:bg-[#2A2A2A] transition-colors">
                        <td className="p-3">
                          <button
                            onClick={() => handleToggleRule(rule)}
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold transition-colors ${
                              rule.enabled
                                ? 'bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40'
                                : 'bg-[#A7A7A7]/20 text-[#A7A7A7] border border-[#A7A7A7]/40'
                            }`}
                          >
                            {rule.enabled ? 'ENABLED' : 'DISABLED'}
                          </button>
                        </td>
                        <td className="p-3 font-medium text-[#F7F7F7]">{rule.name}</td>
                        <td className="p-3 font-mono text-[#A7A7A7]">
                          {rule.service_id
                            ? services.find((s) => s.id === rule.service_id)?.name || rule.service_id
                            : 'GLOBAL (All Services)'}
                        </td>
                        <td className="p-3 font-mono text-[#E50039]">{rule.metric_name}</td>
                        <td className="p-3 font-mono">
                          {rule.operator} {rule.threshold}
                        </td>
                        <td className="p-3 font-mono text-[#A7A7A7]">
                          {rule.window_seconds}s / {rule.cooldown_seconds}s
                        </td>
                        <td className="p-3">
                          <Badge variant={getSeverityBadgeVariant(rule.severity)}>
                            {rule.severity.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="p-3 text-right space-x-2">
                          <button
                            onClick={() => handleDeleteRule(rule.id)}
                            className="text-[#EF4444] hover:underline font-mono text-[11px]"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}



      {/* CREATE ALERT RULE MODAL */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Alert Evaluation Rule"
      >
        <form onSubmit={handleCreateRuleSubmit} className="space-y-4">
          {formError && (
            <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded text-xs text-[#EF4444]">
              {formError}
            </div>
          )}

          <Input
            label="Rule Name"
            type="text"
            value={ruleName}
            onChange={(e) => setRuleName(e.target.value)}
            placeholder="e.g. High HTTP 500 Error Rate"
            required
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col space-y-1.5">
              <label className="text-xs font-medium text-[#A7A7A7]">Target Service</label>
              <select
                value={targetServiceId}
                onChange={(e) => setTargetServiceId(e.target.value)}
                className="w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-xs focus:outline-none focus:border-[#E50039]"
              >
                <option value="">Global Rule (All Services - Admin only)</option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.environment})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col space-y-1.5">
              <label className="text-xs font-medium text-[#A7A7A7]">Metric Name</label>
              <select
                value={metricName}
                onChange={(e) => setMetricName(e.target.value)}
                className="w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-xs focus:outline-none focus:border-[#E50039]"
              >
                <option value="error_rate">error_rate — HTTP failure ratio</option>
                <option value="avg_latency_ms">avg_latency_ms — Response duration (ms)</option>
                <option value="service_health">service_health — Health status state</option>
                <option value="http_requests_total">http_requests_total — Request throughput</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col space-y-1.5">
              <label className="text-xs font-medium text-[#A7A7A7]">Operator</label>
              <select
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                className="w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-xs focus:outline-none focus:border-[#E50039]"
              >
                <option value=">">&gt; (Greater than)</option>
                <option value=">=">&gt;= (Greater than or equal)</option>
                <option value="<">&lt; (Less than)</option>
                <option value="<=">&lt;= (Less than or equal)</option>
                <option value="=">= (Equal to)</option>
              </select>
            </div>

            <Input
              label="Threshold Value"
              type="number"
              step="0.001"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder="0.10"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="flex flex-col space-y-1.5">
              <label className="text-xs font-medium text-[#A7A7A7]">Severity Level</label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as AlertSeverity)}
                className="w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-xs focus:outline-none focus:border-[#E50039]"
              >
                <option value="critical">CRITICAL</option>
                <option value="warning">WARNING</option>
                <option value="info">INFO</option>
              </select>
            </div>

            <Input
              label="Window (seconds)"
              type="number"
              value={windowSeconds}
              onChange={(e) => setWindowSeconds(e.target.value)}
              placeholder="60"
              required
            />

            <Input
              label="Cooldown (seconds)"
              type="number"
              value={cooldownSeconds}
              onChange={(e) => setCooldownSeconds(e.target.value)}
              placeholder="300"
              required
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t border-[#333333]">
            <Button variant="secondary" type="button" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" isLoading={isSubmitting}>
              Create Alert Rule
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};