import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/layout/PageHeader';
import { getServicesApi, createServiceApi, previewGitHubRepositoryApi, deleteServiceApi } from '../services/services';
import { useAuth } from '../app/AuthContext';
import { GitHubRepositoryPreview, Service } from '../types';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { Skeleton } from '../components/ui/Skeleton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { formatDate, safeExtractErrorMessage } from '../lib/utils';

export const Services: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role.toLowerCase() === 'admin';
  const [services, setServices] = useState<Service[]>([]);
  const [search, setSearch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [flow, setFlow] = useState<'manual' | 'github'>('manual');
  const [name, setName] = useState<string>('');
  const [identifier, setIdentifier] = useState<string>('');
  const [environment, setEnvironment] = useState<string>('production');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [repositoryUrl, setRepositoryUrl] = useState<string>('');
  const [githubToken, setGithubToken] = useState<string>('');
  const [githubPreview, setGithubPreview] = useState<GitHubRepositoryPreview | null>(null);
  const [isFetchingRepository, setIsFetchingRepository] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [createdService, setCreatedService] = useState<Service | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
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
        environment,
        base_url: baseUrl.trim() || undefined,
        repository_url: flow === 'github' ? githubPreview?.repository_url : undefined,
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

  const handleRepositoryPreview = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsFetchingRepository(true);
    setFormError(null);
    setGithubPreview(null);
    try {
      const preview = await previewGitHubRepositoryApi(repositoryUrl.trim(), githubToken.trim() || undefined);
      setGithubPreview(preview);
      setRepositoryUrl(preview.repository_url);
      setName(preview.full_name.split('/')[1] || preview.full_name);
      setIdentifier(preview.full_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80));
    } catch (err) {
      setFormError(safeExtractErrorMessage(err));
    } finally {
      setGithubToken('');
      setIsFetchingRepository(false);
    }
  };

  const closeModal = () => {
    setIsModalOpen(false); setCreatedKey(null); setCreatedService(null); setName(''); setIdentifier('');
    setBaseUrl(''); setRepositoryUrl(''); setGithubToken(''); setGithubPreview(null); setFormError(null); setCopied(false);
  };
  const openManual = () => { setFlow('manual'); setIsModalOpen(true); };
  const openGitHub = () => { setFlow('github'); setIsModalOpen(true); };
  const filtered = services.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()));
  const confirmDelete = async () => {
    if (!serviceToDelete) return;
    setIsDeleting(true); setDeleteError(null);
    try { await deleteServiceApi(serviceToDelete.id); setServiceToDelete(null); await fetchServices(); }
    catch (err) { setDeleteError(safeExtractErrorMessage(err)); }
    finally { setIsDeleting(false); }
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
      <PageHeader title="Monitored Services" description="Connect applications and review the telemetry they report." action={<div className="flex flex-wrap gap-2"><Button variant="secondary" size="sm" onClick={openGitHub}>Connect GitHub repository</Button><Button size="sm" onClick={openManual}>Register service</Button></div>} />
      <div className="flex items-center justify-between gap-4">
        <Input placeholder="Filter..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-md" />
        <span className="text-xs font-mono text-[#A7A7A7]">Total: {filtered.length}</span>
      </div>
      {isLoading ? <Skeleton className="h-64 w-full" /> : error ? <ErrorState message={error} onRetry={fetchServices} /> : filtered.length === 0 ? (
        <EmptyState title="No Monitored Services" description="Connect a GitHub repository or register a service manually to start receiving telemetry." actionLabel="Connect GitHub" onAction={openGitHub} />
      ) : (
        <Table>
          <TableHeader><TableRow><TableHead>Service</TableHead><TableHead>Identifier</TableHead><TableHead>Source</TableHead><TableHead>Environment</TableHead><TableHead>Status</TableHead><TableHead>Last Seen</TableHead>{isAdmin && <TableHead>Actions</TableHead>}</TableRow></TableHeader>
          <TableBody>
            {filtered.map((s) => (
              <TableRow key={s.id}>
                <TableCell><button className="font-semibold text-left hover:text-[#E50039] focus-visible:outline" onClick={() => navigate(`/app/services/${s.id}`)}>{s.name}</button></TableCell>
                <TableCell className="font-mono text-[#A7A7A7]">{s.identifier}</TableCell>
                <TableCell>{s.repository_url ? <a href={s.repository_url} target="_blank" rel="noreferrer" className="text-[#E50039] hover:underline" onClick={(event) => event.stopPropagation()}>GitHub ↗</a> : <span className="text-[#777]">Manual</span>}</TableCell>
                <TableCell>{s.environment}</TableCell>
                <TableCell><StatusIndicator status={s.status} /></TableCell>
                <TableCell>{formatDate(s.last_seen_at)}</TableCell>
                {isAdmin && <TableCell><Button variant="danger" size="sm" onClick={() => { setDeleteError(null); setServiceToDelete(s); }}>Delete</Button></TableCell>}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={createdKey ? 'Connect your application' : flow === 'github' ? 'Connect GitHub repository' : 'Register service'} className="max-w-2xl">
        {createdKey ? (
          <div className="space-y-4">
            <div className="border border-[#10B981]/30 bg-[#10B981]/10 p-3 text-sm text-[#10B981]">Service created. Copy this ingestion key now; NexPulse will not show it again.</div>
            {createdService?.repository_url && <a href={createdService.repository_url} target="_blank" rel="noreferrer" className="text-sm text-[#F7F7F7] underline decoration-[#E50039] underline-offset-4">{createdService.repository_url}</a>}
            <div className="flex gap-2"><div className="min-w-0 flex-1 break-all border border-[#333333] bg-[#262626] p-3 font-mono text-xs text-[#E50039]">{createdKey}</div><Button variant="secondary" size="sm" onClick={() => { void navigator.clipboard.writeText(createdKey).then(() => setCopied(true)).catch(() => setFormError('Clipboard access failed. Select and copy the key manually.')); }}>{copied ? 'Copied' : 'Copy key'}</Button></div>
            <p className="text-xs text-[#A7A7A7]">Store the key as a secret in your app’s hosting platform or GitHub Actions. Never commit it to the repository or expose it to browser code.</p>
            <div><p className="mb-2 text-xs font-mono uppercase text-[#A7A7A7]">PowerShell · send a first signal</p><pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all border border-[#333333] bg-[#191919] p-3 text-xs text-[#F7F7F7]">{powershellSignal(createdService?.identifier || '')}</pre><Button variant="secondary" size="sm" onClick={() => { void navigator.clipboard.writeText(powershellSignal(createdService?.identifier || '')).then(() => setCopied(true)).catch(() => setFormError('Clipboard access failed. Select and copy the command manually.')); }}>Copy PowerShell command</Button></div>
            <p className="text-xs text-[#A7A7A7]">Fetching a repository does not run or instrument its code. Add telemetry reporting to the server-side runtime and send signals to this endpoint to populate NexPulse.</p>
            <Button className="w-full" onClick={closeModal}>Done</Button>
          </div>
        ) : flow === 'github' ? (
          <div className="space-y-4">
            {!githubPreview ? <form onSubmit={handleRepositoryPreview} className="space-y-4">
              <p className="text-sm text-[#A7A7A7]">Fetch repository metadata and detect common project manifests. NexPulse never clones or executes source code.</p>
              <Input label="GitHub repository URL" type="url" value={repositoryUrl} onChange={(e) => setRepositoryUrl(e.target.value)} placeholder="https://github.com/owner/repository" required />
              <Input label="Read-only token (private repos only)" type="password" autoComplete="off" value={githubToken} onChange={(e) => setGithubToken(e.target.value)} placeholder="Fine-grained GitHub token (optional)" />
              <p className="-mt-2 text-xs text-[#777]">Use a fine-grained token limited to this repository with Metadata and Contents read-only access. It is sent only for this lookup and is not saved by NexPulse.</p>
              {formError && <p role="alert" className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-3 text-sm text-[#EF4444]">{formError}</p>}
              <Button type="submit" className="w-full" isLoading={isFetchingRepository}>Fetch repository details</Button>
            </form> : <form onSubmit={handleCreate} className="space-y-4">
              <div className="border border-[#333333] bg-[#262626] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">{githubPreview.full_name}</h3><span className="text-xs text-[#A7A7A7]">{githubPreview.private ? 'Private' : 'Public'} · {githubPreview.default_branch}</span></div>
                {githubPreview.description && <p className="mt-2 text-sm text-[#A7A7A7]">{githubPreview.description}</p>}
                <p className="mt-3 text-xs text-[#A7A7A7]">Language: {githubPreview.language || 'Not detected'} · Root manifests: {githubPreview.manifest_files.length ? githubPreview.manifest_files.join(', ') : 'None detected'}</p>
                {githubPreview.archived && <p className="mt-2 text-xs text-[#F59E0B]">This repository is archived. You can still link it, but its runtime will need to send telemetry separately.</p>}
                <button type="button" className="mt-3 text-xs text-[#E50039] underline" onClick={() => { setGithubPreview(null); setFormError(null); }}>Choose a different repository</button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Service name" value={name} onChange={(e) => setName(e.target.value)} required />
                <Input label="Service identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} maxLength={80} required />
              </div>
              <div><label className="mb-1 block text-xs text-[#A7A7A7]">Environment</label><select value={environment} onChange={(e) => setEnvironment(e.target.value)} className="h-9 w-full border border-[#333333] bg-[#1F1F1F] px-3 text-sm text-[#F7F7F7]"><option value="production">Production</option><option value="staging">Staging</option><option value="development">Development</option></select></div>
              <Input label="Running application URL (optional)" type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.example.com" />
              <p className="text-xs text-[#A7A7A7]">This URL is for the deployed service, not the GitHub repository. Repository link and runtime URL are stored separately.</p>
              {formError && <p role="alert" className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-3 text-sm text-[#EF4444]">{formError}</p>}
              <Button type="submit" className="w-full" isLoading={isSubmitting}>Create monitored service</Button>
            </form>}
          </div>
        ) : (
          <form onSubmit={handleCreate} className="space-y-4">
            <Input label="Service Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Order Service" required />
            <Input label="Service Identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="order-service" maxLength={80} required />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-[#A7A7A7]">Env</label>
                <select value={environment} onChange={(e) => setEnvironment(e.target.value)} className="w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-sm">
                  <option value="production">Production</option>
                  <option value="staging">Staging</option>
                </select>
              </div>
            </div>
            <Input label="Base URL (optional)" type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.example.com" />
            {formError && <p role="alert" className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-3 text-sm text-[#EF4444]">{formError}</p>}
            <Button type="submit" className="w-full" isLoading={isSubmitting}>Register Service</Button>
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
