import React, { useCallback, useEffect, useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { useAuth } from '../app/AuthContext';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { getServicesApi } from '../services/services';
import { apiFetch } from '../services/api';
import { Service } from '../types';
import { safeExtractErrorMessage } from '../lib/utils';

interface HealthResponse { status: string; service: string; version: string; environment: string; dependencies?: { database?: string; redis?: string } }

export const Settings: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [serviceData, healthData] = await Promise.all([getServicesApi(), apiFetch<HealthResponse>('/health')]);
      setServices(serviceData);
      setHealth(healthData);
    } catch (err) { setError(safeExtractErrorMessage(err)); setHealth(null); }
  }, []);

  useEffect(() => {
    void refresh();
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(query.matches);
    update(); query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, [refresh]);

  const section = 'rounded border border-[#333333] bg-[#1F1F1F] p-5 sm:p-6';
  const label = 'text-[10px] font-mono uppercase tracking-[.16em] text-[#A7A7A7]';
  return <div className="space-y-6">
    <PageHeader title="Workspace Settings" description="Operator identity, current session, telemetry connection, and system availability." action={<Button size="sm" variant="secondary" onClick={() => void refresh()}>Refresh status</Button>} />

    <section className={section} aria-labelledby="settings-account"><div className="mb-5 flex items-center justify-between"><h2 id="settings-account" className="text-sm font-semibold font-mono uppercase">Account</h2><Badge variant={user?.is_active ? 'healthy' : 'critical'}>{user?.is_active ? 'Active' : 'Unavailable'}</Badge></div>
      {user ? <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2"><div><dt className={label}>Full name</dt><dd className="mt-1 font-medium">{user.full_name}</dd></div><div><dt className={label}>Email</dt><dd className="mt-1 break-all font-medium">{user.email}</dd></div><div><dt className={label}>Role</dt><dd className="mt-1"><Badge variant="info">{user.role}</Badge></dd></div><div><dt className={label}>Account state</dt><dd className="mt-1">{user.is_active ? 'Enabled' : 'Suspended'}</dd></div></dl> : <p className="text-sm text-[#A7A7A7]">No authenticated operator is available.</p>}
    </section>

    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <section className={section} aria-labelledby="settings-session"><h2 id="settings-session" className="mb-5 text-sm font-semibold font-mono uppercase">Session & security</h2>
        <dl className="space-y-4"><div className="flex items-center justify-between gap-4"><dt className="text-sm text-[#A7A7A7]">Authentication</dt><dd><Badge variant={isAuthenticated ? 'healthy' : 'critical'}>{isAuthenticated ? 'Signed in' : 'Signed out'}</Badge></dd></div><div className="flex items-center justify-between gap-4"><dt className="text-sm text-[#A7A7A7]">Session storage</dt><dd className="text-right text-sm">HttpOnly cookie</dd></div><div className="flex items-center justify-between gap-4"><dt className="text-sm text-[#A7A7A7]">Token visibility</dt><dd className="text-right text-sm">Unavailable to JavaScript</dd></div></dl>
        <Button className="mt-6" variant="secondary" onClick={() => void logout()}>Sign out of this session</Button>
      </section>

      <section className={section} aria-labelledby="settings-telemetry"><h2 id="settings-telemetry" className="mb-5 text-sm font-semibold font-mono uppercase">Telemetry</h2>
        <dl className="space-y-4"><div className="flex items-center justify-between gap-4"><dt className="text-sm text-[#A7A7A7]">Registered services</dt><dd className="font-mono">{services.length}</dd></div><div className="flex items-center justify-between gap-4"><dt className="text-sm text-[#A7A7A7]">Ingestion credentials</dt><dd className="text-right text-sm">Stored securely · never shown</dd></div><div className="flex items-center justify-between gap-4"><dt className="text-sm text-[#A7A7A7]">Last known service signals</dt><dd className="font-mono">{services.filter((service) => service.last_seen_at).length}</dd></div></dl>
        {error && <p role="status" className="mt-4 text-sm text-[#EF4444]">Service inventory unavailable: {error}</p>}
      </section>
    </div>

    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <section className={section} aria-labelledby="settings-preferences"><h2 id="settings-preferences" className="mb-5 text-sm font-semibold font-mono uppercase">Preferences</h2><div className="flex items-center justify-between gap-4"><div><p className="text-sm">Reduced motion</p><p className="mt-1 text-xs text-[#A7A7A7]">Read from your operating system accessibility preference.</p></div><Badge variant={reducedMotion ? 'info' : 'neutral'}>{reducedMotion ? 'Enabled' : 'System default'}</Badge></div><p className="mt-4 border-t border-[#333333] pt-4 text-xs text-[#777]">Theme and saved workspace preferences are not configured for this account.</p></section>
      <section className={section} aria-labelledby="settings-system"><h2 id="settings-system" className="mb-5 text-sm font-semibold font-mono uppercase">System availability</h2>
        {health ? <><div className="flex items-center justify-between"><span className="text-sm text-[#A7A7A7]">Backend API</span><Badge variant={health.status === 'healthy' ? 'healthy' : 'warning'}>{health.status}</Badge></div><dl className="mt-4 grid grid-cols-2 gap-4"><div><dt className={label}>Environment</dt><dd className="mt-1 text-sm">{health.environment}</dd></div><div><dt className={label}>Version</dt><dd className="mt-1 font-mono text-sm">{health.version}</dd></div><div><dt className={label}>Database</dt><dd className="mt-1 text-sm">{health.dependencies?.database || 'Not reported'}</dd></div><div><dt className={label}>Queue/cache</dt><dd className="mt-1 text-sm">{health.dependencies?.redis || 'Not reported'}</dd></div></dl></> : <p role="status" className="text-sm text-[#A7A7A7]">{error ? 'Backend status could not be verified.' : 'Checking backend status…'}</p>}
      </section>
    </div>
  </div>;
};
