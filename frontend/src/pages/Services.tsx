import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/layout/PageHeader';
import { getServicesApi, createServiceApi, deleteServiceApi } from '../services/services';
import { useAuth } from '../app/AuthContext';
import { Service } from '../types';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { formatDate, safeExtractErrorMessage } from '../lib/utils';
import { sendConnectionTestApi } from '../services/telemetry';

export const Services: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role.toLowerCase() === 'admin';
  const [services, setServices] = useState<Service[]>([]);
  const [search, setSearch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [identifier, setIdentifier] = useState<string>('');
  const [environment, setEnvironment] = useState<string>('production');
  const [framework, setFramework] = useState<string>('');
  const [language, setLanguage] = useState<string>('');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [identifierManuallyEdited, setIdentifierManuallyEdited] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [createdService, setCreatedService] = useState<Service | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [connectionTestState, setConnectionTestState] = useState<'idle' | 'testing' | 'passed' | 'failed'>('idle');
  const [connectionTestMessage, setConnectionTestMessage] = useState<string | null>(null);
  const [serviceToDelete, setServiceToDelete] = useState<Service | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchServices = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setServices(await getServicesApi());
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchServices(); }, [fetchServices]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !identifier.trim()) return;
    setIsSubmitting(true);
    setFormError(null);
    try {
      const s = await createServiceApi({
        identifier: identifier.trim(),
        name: name.trim(),
        description: description.trim() || undefined,
        framework: framework.trim() || undefined,
        language: language.trim() || undefined,
        environment,
        base_url: baseUrl.trim() || undefined,
      });
      if (s.ingest_key) {
        setCreatedKey(s.ingest_key);
        setCreatedService(s);
      }
      else setIsModalOpen(false);
      await fetchServices();
    } catch (err) {
      setFormError(safeExtractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const closeModal = () => {
    setIsModalOpen(false); setCreatedKey(null); setCreatedService(null); setName(''); setDescription(''); setIdentifier('');
    setBaseUrl(''); setFormError(null); setCopied(false); setFramework(''); setLanguage(''); setIdentifierManuallyEdited(false); setConnectionTestState('idle'); setConnectionTestMessage(null);
  };
  const openConnect = () => { setIsModalOpen(true); };
  const filtered = services.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()));
  const confirmDelete = async () => {
    if (!serviceToDelete) return;
    setIsDeleting(true); setDeleteError(null);
    try { await deleteServiceApi(serviceToDelete.id); setServiceToDelete(null); await fetchServices(); }
    catch (err) { setDeleteError(safeExtractErrorMessage(err)); }
    finally { setIsDeleting(false); }
  };
  const testConnection = async () => {
    if (!createdKey || !createdService?.identifier) return;
    setConnectionTestState('testing'); setConnectionTestMessage(null);
    try {
      const result = await sendConnectionTestApi(createdService.id, createdService.identifier, createdKey);
      setConnectionTestState('passed');
      setConnectionTestMessage(`Connection accepted. ${result.accepted_count} event persisted.`);
      await fetchServices();
    } catch (err) {
      setConnectionTestState('failed');
      setConnectionTestMessage(safeExtractErrorMessage(err));
    }
  };
  const powershellSignal = (serviceIdentifier: string) => {
    const safeIdentifier = serviceIdentifier.replace(/`/g, '``').replace(/"/g, '`"');
    return `$key = Read-Host "Paste the ingestion key for ${safeIdentifier}"
$body = @{
  service_id = "${safeIdentifier}"
  method = "GET"
  endpoint = "/health"
  status_code = 200
  duration_ms = 12
  outcome = "success"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "${window.location.origin}/api/v1/telemetry/events" -Headers @{ "X-Ingest-Key" = $key } -ContentType "application/json" -Body $body`;
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Monitored Services" description="Connect applications and review the telemetry they report." action={<div className="flex flex-wrap gap-2"><Button variant="secondary" size="sm" onClick={() => void fetchServices()} isLoading={isLoading}>Refresh</Button><Button size="sm" onClick={openConnect}>Connect application</Button></div>} />
      <div className="flex items-center justify-between gap-4">
        <Input placeholder="Filter..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-md" />
        <span className="text-xs font-mono text-[#A7A7A7]">Total: {filtered.length}</span>
      </div>
      {isLoading ? <Skeleton className="h-64 w-full" /> : error ? <ErrorState message={error} onRetry={fetchServices} /> : filtered.length === 0 ? (
        <EmptyState title="No Monitored Services" description="Add your application, save its private ingestion key, then send a test signal to verify the connection." actionLabel="Connect application" onAction={openConnect} />
      ) : (
        <Table>
          <TableHeader><TableRow><TableHead>Service</TableHead><TableHead>Identifier</TableHead><TableHead>Environment</TableHead><TableHead>Status</TableHead><TableHead>Last Signal</TableHead>{isAdmin && <TableHead>Actions</TableHead>}</TableRow></TableHeader>
          <TableBody>
            {filtered.map((s) => (
              <TableRow key={s.id}>
                <TableCell><button className="font-semibold text-left hover:text-[#E50039] focus-visible:outline" onClick={() => navigate(`/app/services/${s.id}`)}>{s.name}</button></TableCell>
                <TableCell className="font-mono text-[#A7A7A7]">{s.identifier}</TableCell>
                <TableCell>{s.environment}</TableCell>
                <TableCell>{s.is_active === false ? <span className="text-[#EF4444]">Inactive</span> : !s.last_seen_at ? <span className="text-[#A7A7A7]">Never connected</span> : Date.now() - new Date(s.last_seen_at).getTime() < 5 * 60 * 1000 ? <span className="text-[#10B981]">Receiving</span> : <span className="text-[#F59E0B]">Stale</span>}</TableCell>
                <TableCell>{formatDate(s.last_seen_at)}</TableCell>
                {isAdmin && <TableCell><Button variant="danger" size="sm" onClick={() => { setDeleteError(null); setServiceToDelete(s); }}>Delete</Button></TableCell>}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={createdKey ? 'Connect your application' : 'Connect application'} className="max-w-2xl">
        {createdKey ? (
          <div className="space-y-4">
            <div className="border border-[#10B981]/30 bg-[#10B981]/10 p-3 text-sm text-[#10B981]">Service created. Copy this ingestion key now; NexPulse will not show it again.</div>
            <p className="text-sm text-[#A7A7A7]">Add these values to your app host’s secret settings. The API URL ends at <code>/telemetry</code>; NexPulse adds the event, metric, or log route.</p>
            <pre className="overflow-auto whitespace-pre-wrap break-all border border-[#333333] bg-[#191919] p-3 text-xs text-[#F7F7F7]">{`NEXPULSE_API_URL = "${window.location.origin}/api/v1/telemetry"\nNEXPULSE_SERVICE_ID = "${createdService?.identifier || ''}"\nNEXPULSE_INGEST_KEY = "${createdKey}"`}</pre>
            <p className="text-xs text-[#A7A7A7]">For Streamlit, paste the TOML values above into App settings → Secrets. Copy <code>nexpulse_client.py</code> from NexPulse’s examples into your app, then initialize it in server-side Python:</p>
            <pre className="overflow-auto whitespace-pre-wrap break-all border border-[#333333] bg-[#191919] p-3 text-xs text-[#F7F7F7]">{`import streamlit as st\nfrom nexpulse_client import NexPulseClient\n\nnexpulse = NexPulseClient(\n    api_url=st.secrets["NEXPULSE_API_URL"],\n    service_id=st.secrets["NEXPULSE_SERVICE_ID"],\n    ingest_key=st.secrets["NEXPULSE_INGEST_KEY"],\n)\n\nnexpulse.send("events", {\n    "method": "POST", "endpoint": "/your/action",\n    "status_code": 200, "duration_ms": 120, "outcome": "success",\n})`}</pre>
            <div className="flex gap-2"><div className="min-w-0 flex-1 break-all border border-[#333333] bg-[#262626] p-3 font-mono text-xs text-[#E50039]">{createdKey}</div><Button variant="secondary" size="sm" onClick={() => { void navigator.clipboard.writeText(createdKey).then(() => setCopied(true)).catch(() => setFormError('Clipboard access failed. Select and copy the key manually.')); }}>{copied ? 'Copied' : 'Copy key'}</Button></div>
            <p className="text-xs text-[#A7A7A7]">Keep the key in server-side secrets only. Never commit it or expose it to browser JavaScript.</p>
            <div className="rounded border border-[#333333] bg-[#1F1F1F] p-3"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold">Test connection</p><p className="text-xs text-[#A7A7A7]">Sends and stores one labeled test event using this key.</p></div><Button variant="secondary" size="sm" disabled={connectionTestState === 'testing'} isLoading={connectionTestState === 'testing'} onClick={() => void testConnection()}>Send test event</Button></div>{connectionTestMessage && <p role={connectionTestState === 'failed' ? 'alert' : 'status'} className={`mt-2 text-sm ${connectionTestState === 'failed' ? 'text-[#EF4444]' : 'text-[#10B981]'}`}>{connectionTestMessage}</p>}</div>
            <div><p className="mb-2 text-xs font-mono uppercase text-[#A7A7A7]">PowerShell · send a first signal</p><pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all border border-[#333333] bg-[#191919] p-3 text-xs text-[#F7F7F7]">{powershellSignal(createdService?.identifier || '')}</pre><Button variant="secondary" size="sm" onClick={() => { void navigator.clipboard.writeText(powershellSignal(createdService?.identifier || '')).then(() => setCopied(true)).catch(() => setFormError('Clipboard access failed. Select and copy the command manually.')); }}>Copy PowerShell command</Button></div>
            <p className="text-xs text-[#A7A7A7]">The test verifies that NexPulse accepts and stores a signal. To monitor real traffic, add the same server-side telemetry client to your application’s request handlers.</p>
            <Button className="w-full" onClick={closeModal}>Done</Button>
          </div>
        ) : (
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="rounded border border-[#333333] bg-[#1F1F1F] p-3 text-sm text-[#A7A7A7]">Create a service identity, save its private key, and run the built-in connection check. No repository access or code execution is required.</div>
            <Input label="Application name" value={name} onChange={(e) => { const value = e.target.value; setName(value); if (!identifierManuallyEdited) setIdentifier(value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80)); }} placeholder="Study Planner" required />
            <Input label="Service identifier" value={identifier} onChange={(e) => { setIdentifierManuallyEdited(true); setIdentifier(e.target.value); }} placeholder="study-planner" maxLength={80} required />
            <Input label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} placeholder="What this application does" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-[#A7A7A7]">Env</label>
                <select value={environment} onChange={(e) => setEnvironment(e.target.value)} className="w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-sm">
                  <option value="production">Production</option>
                  <option value="staging">Staging</option>
                  <option value="development">Development</option>
                </select>
              </div>
            </div>
            <Input label="Public application URL (optional)" type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://your-app.example.com" />
            <div className="grid gap-4 sm:grid-cols-2"><Input label="Framework (optional)" value={framework} onChange={(e) => setFramework(e.target.value)} placeholder="Streamlit, FastAPI, Express…" /><Input label="Language (optional)" value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="Python, JavaScript…" /></div>
            {formError && <p role="alert" className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-3 text-sm text-[#EF4444]">{formError}</p>}
            <Button type="submit" className="w-full" isLoading={isSubmitting}>Create service and get connection key</Button>
          </form>
        )}
      </Modal>
      <Modal isOpen={!!serviceToDelete} onClose={() => { if (!isDeleting) { setServiceToDelete(null); setDeleteError(null); } }} title="Delete monitored service" className="max-w-lg">
        <div className="space-y-4">
          <p className="text-sm text-[#F7F7F7]">Permanently delete <strong>{serviceToDelete?.name}</strong> ({serviceToDelete?.identifier})?</p>
          <p className="text-sm text-[#EF4444]">This also deletes its telemetry, metrics, logs, alert rules, alert history, incidents, and ingestion key. This cannot be undone.</p>
          {deleteError && <p role="alert" className="text-sm text-[#EF4444]">{deleteError}</p>}
          <div className="flex justify-end gap-2"><Button variant="secondary" disabled={isDeleting} onClick={() => setServiceToDelete(null)}>Cancel</Button><Button variant="danger" isLoading={isDeleting} onClick={() => void confirmDelete()}>Delete service and data</Button></div>
        </div>
      </Modal>
    </div>
  );
};
