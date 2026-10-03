import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '../components/layout/PageHeader';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { Input } from '../components/ui/Input';
import { Incident, IncidentEvent, IncidentStatus, AlertSeverity, Service } from '../types';
import {
  fetchIncidentsApi,
  fetchIncidentDetailApi,
  updateIncidentApi,
  fetchIncidentEventsApi,
  addIncidentNoteApi,
} from '../services/incidents';
import { AIAnalysisPanel } from '../components/ui/AIAnalysisPanel';
import { getServicesApi } from '../services/services';

export const Incidents: React.FC = () => {
  const navigate = useNavigate();
  const { incidentId } = useParams();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedServiceId, setSelectedServiceId] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');

  // Selected Incident for Detail Panel / Modal
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<IncidentEvent[]>([]);
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);

  // Form states for updates inside Detail modal
  const [newNote, setNewNote] = useState<string>('');
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [resolutionNote, setResolutionNote] = useState<string>('');
  const [showResolutionForm, setShowResolutionForm] = useState<boolean>(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);

  const loadIncidents = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await fetchIncidentsApi({
        service_id: selectedServiceId || undefined,
        status: selectedStatus || undefined,
        severity: selectedSeverity || undefined,
      });
      setIncidents(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch incidents';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [selectedServiceId, selectedStatus, selectedSeverity]);

  useEffect(() => {
    getServicesApi()
      .then(setServices)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadIncidents();
  }, [loadIncidents]);

  useEffect(() => {
    if (!incidentId) { setIsDetailOpen(false); return; }
    let active = true;
    setIsDetailOpen(true);
    setIsDetailLoading(true);
    Promise.all([fetchIncidentDetailApi(incidentId), fetchIncidentEventsApi(incidentId)])
      .then(([detail, events]) => { if (active) { setSelectedIncident(detail); setTimelineEvents(events); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : 'Could not load incident details.'); })
      .finally(() => { if (active) setIsDetailLoading(false); });
    return () => { active = false; };
  }, [incidentId]);

  const openIncidentDetail = (inc: Incident) => {
    navigate(`/app/incidents/${inc.id}`);
    setSelectedIncident(inc);
    setIsDetailOpen(true);
    setShowResolutionForm(false);
    setResolutionNote('');
    setNewNote('');
  };

  const handleStatusTransition = async (targetStatus: IncidentStatus) => {
    if (!selectedIncident) return;
    if (targetStatus === 'resolved' && !showResolutionForm) {
      setShowResolutionForm(true);
      return;
    }

    try {
      setIsUpdatingStatus(true);
      const updated = await updateIncidentApi(selectedIncident.id, {
        status: targetStatus,
        resolution_note: targetStatus === 'resolved' ? resolutionNote : undefined,
      });
      setSelectedIncident(updated);
      setShowResolutionForm(false);
      const events = await fetchIncidentEventsApi(selectedIncident.id);
      setTimelineEvents(events);
      await loadIncidents();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update incident status';
      alert(msg);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIncident || !newNote.trim()) return;

    try {
      setIsAddingNote(true);
      await addIncidentNoteApi(selectedIncident.id, newNote.trim());
      setNewNote('');
      const events = await fetchIncidentEventsApi(selectedIncident.id);
      setTimelineEvents(events);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to add timeline note';
      alert(msg);
    } finally {
      setIsAddingNote(false);
    }
  };

  const getStatusBadgeVariant = (status: IncidentStatus): 'warning' | 'info' | 'healthy' | 'neutral' => {
    switch (status) {
      case 'open':
        return 'warning';
      case 'investigating':
        return 'info';
      case 'resolved':
        return 'healthy';
      default:
        return 'neutral';
    }
  };

  const getSeverityBadgeVariant = (severity: AlertSeverity): 'critical' | 'warning' | 'info' | 'neutral' => {
    switch (severity) {
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
        title="Incidents"
        description="Incident lifecycle management, automated escalation, root cause timeline logging, and resolution tracking."
      />

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-[#1F1F1F] border border-[#333333] rounded">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedServiceId}
            onChange={(e) => setSelectedServiceId(e.target.value)}
            className="bg-[#191919] border border-[#333333] text-[#F7F7F7] text-xs px-3 py-2 rounded focus:outline-none focus:border-[#E50039]"
          >
            <option value="">All Services</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="bg-[#191919] border border-[#333333] text-[#F7F7F7] text-xs px-3 py-2 rounded focus:outline-none focus:border-[#E50039]"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
          </select>

          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="bg-[#191919] border border-[#333333] text-[#F7F7F7] text-xs px-3 py-2 rounded focus:outline-none focus:border-[#E50039]"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>

        <Button variant="secondary" size="sm" onClick={loadIncidents}>
          Refresh
        </Button>
      </div>

      {/* Content States */}
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : error ? (
        <ErrorState message={error} onRetry={loadIncidents} />
      ) : incidents.length === 0 ? (
        <EmptyState
          title="No Incidents Found"
          description="There are currently no active or historical incidents matching your filter criteria."
        />
      ) : (
        <div className="bg-[#1F1F1F] border border-[#333333] rounded overflow-hidden">
          <table className="w-full text-left text-xs text-[#F7F7F7]">
            <thead className="bg-[#262626] text-[#A7A7A7] uppercase font-mono border-b border-[#333333]">
              <tr>
                <th className="p-3">Title / Service</th>
                <th className="p-3">Severity</th>
                <th className="p-3">Status</th>
                <th className="p-3">Opened</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#333333]">
              {incidents.map((inc) => (
                <tr
                  key={inc.id}
                  onClick={() => openIncidentDetail(inc)}
                  className="hover:bg-[#262626] cursor-pointer transition-colors"
                >
                  <td className="p-3 font-medium">
                    <div className="text-[#F7F7F7] font-semibold">{inc.title}</div>
                    <div className="text-[#A7A7A7] text-[11px] font-mono">
                      Service: {inc.service_name || inc.service_id}
                    </div>
                  </td>
                  <td className="p-3">
                    <Badge variant={getSeverityBadgeVariant(inc.severity)}>{inc.severity}</Badge>
                  </td>
                  <td className="p-3">
                    <Badge variant={getStatusBadgeVariant(inc.status)}>{inc.status}</Badge>
                  </td>
                  <td className="p-3 text-[#A7A7A7] font-mono">
                    {new Date(inc.opened_at).toLocaleString()}
                  </td>
                  <td className="p-3 text-right">
                    <Button variant="outline" size="sm" onClick={(e) => { e.stopPropagation(); openIncidentDetail(inc); }}>
                      Investigate
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {/* Detail & Action Modal */}
      {selectedIncident && (
        <Modal
          isOpen={isDetailOpen}
          onClose={() => { setIsDetailOpen(false); if (incidentId) navigate('/app/incidents'); }}
          title={`Incident: ${selectedIncident.title}`}
          className="max-w-2xl"
        >
          {isDetailLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <div className="space-y-6 text-xs text-[#F7F7F7]">
              {/* Incident Header Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#191919] p-3 rounded border border-[#333333]">
                <div>
                  <div className="text-[#A7A7A7] font-mono">Status</div>
                  <div className="mt-1">
                    <Badge variant={getStatusBadgeVariant(selectedIncident.status)}>
                      {selectedIncident.status}
                    </Badge>
                  </div>
                </div>
                <div>
                  <div className="text-[#A7A7A7] font-mono">Severity</div>
                  <div className="mt-1">
                    <Badge variant={getSeverityBadgeVariant(selectedIncident.severity)}>
                      {selectedIncident.severity}
                    </Badge>
                  </div>
                </div>
                <div>
                  <div className="text-[#A7A7A7] font-mono">Opened At</div>
                  <div className="mt-1 font-mono text-[#F7F7F7]">
                    {new Date(selectedIncident.opened_at).toLocaleTimeString()}
                  </div>
                </div>
                <div>
                  <div className="text-[#A7A7A7] font-mono">Assignee</div>
                  <div className="mt-1 text-[#F7F7F7]">
                    {selectedIncident.assignee_name || selectedIncident.assignee_email || 'Unassigned'}
                  </div>
                </div>
              </div>

              {/* Status Actions */}
              {selectedIncident.status !== 'resolved' && (
                <div className="p-4 bg-[#262626] border border-[#333333] rounded space-y-3">
                  <div className="font-mono text-xs text-[#A7A7A7] uppercase">Lifecycle Controls</div>
                  <div className="flex flex-wrap gap-2">
                    {selectedIncident.status === 'open' && (
                      <Button
                        variant="secondary"
                        size="sm"
                        isLoading={isUpdatingStatus}
                        onClick={() => handleStatusTransition('investigating')}
                      >
                        Start Investigation
                      </Button>
                    )}
                    <Button
                      variant="primary"
                      size="sm"
                      isLoading={isUpdatingStatus}
                      onClick={() => handleStatusTransition('resolved')}
                    >
                      Resolve Incident
                    </Button>
                  </div>

                  {showResolutionForm && (
                    <div className="space-y-2 mt-3 pt-3 border-t border-[#333333]">
                      <Input
                        label="Resolution Note"
                        value={resolutionNote}
                        onChange={(e) => setResolutionNote(e.target.value)}
                        placeholder="Describe root cause and remediation applied..."
                      />
                      <div className="flex gap-2">
                        <Button
                          variant="primary"
                          size="sm"
                          isLoading={isUpdatingStatus}
                          onClick={() => handleStatusTransition('resolved')}
                        >
                          Confirm Resolution
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowResolutionForm(false)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Evidence Snapshot */}
              {selectedIncident.evidence && (
                <div className="space-y-2">
                  <div className="font-mono text-xs text-[#A7A7A7] uppercase">Originating Evidence</div>
                  <pre className="p-3 bg-[#191919] border border-[#333333] rounded font-mono text-[11px] text-[#A7A7A7] overflow-x-auto">
                    {JSON.stringify(selectedIncident.evidence, null, 2)}
                  </pre>
                </div>
              )}
              {/* AI Assistant Analysis Panel */}
              <AIAnalysisPanel incidentId={selectedIncident.id} />

              {/* Timeline Stream */}
              <div className="space-y-3 pt-2">
                <div className="font-mono text-xs text-[#A7A7A7] uppercase border-b border-[#333333] pb-2">
                  Incident Timeline
                </div>

                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {timelineEvents.map((ev) => (
                    <div key={ev.id} className="p-3 bg-[#191919] border border-[#333333] rounded space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-mono text-[#E50039] uppercase">{ev.event_type}</span>
                        <span className="text-[#A7A7A7] font-mono">
                          {new Date(ev.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-[#F7F7F7] text-xs">{ev.message}</div>
                      {ev.actor_name && (
                        <div className="text-[#A7A7A7] text-[10px] font-mono">Actor: {ev.actor_name}</div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Add Timeline Note Form */}
                <form onSubmit={handleAddNote} className="flex gap-2 pt-2">
                  <Input
                    className="flex-1"
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Add an investigation note..."
                  />
                  <Button type="submit" variant="secondary" size="sm" isLoading={isAddingNote}>
                    Post Note
                  </Button>
                </form>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
};


