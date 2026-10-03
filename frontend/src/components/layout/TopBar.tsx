import React, { useEffect, useState } from 'react';
import { useAuth } from '../../app/AuthContext';
import { Button } from '../ui/Button';
import { StatusIndicator } from '../ui/StatusIndicator';
import { apiFetch } from '../../services/api';

export interface TopBarProps {
  onToggleMobileMenu?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onToggleMobileMenu }) => {
  const { user, logout } = useAuth();
  const [engineStatus, setEngineStatus] = useState<'checking' | 'healthy' | 'unavailable'>('checking');

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const result = await apiFetch<{ status: string }>('/health', { timeoutMs: 5000 });
        if (active) setEngineStatus(result.status === 'healthy' ? 'healthy' : 'unavailable');
      } catch { if (active) setEngineStatus('unavailable'); }
    };
    void check();
    const timer = window.setInterval(check, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  return (
    <header className="h-14 bg-[#1F1F1F] border-b border-[#333333] px-4 flex items-center justify-between">
      <div className="flex items-center space-x-3">
        {/* Mobile menu toggle */}
        <button
          onClick={onToggleMobileMenu}
          className="md:hidden p-1.5 rounded bg-[#262626] text-[#A7A7A7] hover:text-[#F7F7F7] border border-[#333333]"
          aria-label="Toggle navigation menu"
        >
          <span className="font-mono text-xs">MENU</span>
        </button>

        {/* Global operational status */}
        <div className="hidden sm:flex items-center space-x-2 bg-[#262626] border border-[#333333] px-2.5 py-1 rounded">
          <StatusIndicator status={engineStatus === 'healthy' ? 'healthy' : engineStatus === 'unavailable' ? 'critical' : 'degraded'} showLabel={false} />
          <span className="text-xs font-mono text-[#A7A7A7]">{engineStatus === 'healthy' ? 'Backend API Online' : engineStatus === 'unavailable' ? 'Backend API Unavailable' : 'Checking Backend API'}</span>
        </div>
      </div>

      {/* User Info & Actions */}
      <div className="flex items-center space-x-3">
        {user && (
          <div className="flex items-center space-x-2 text-right">
            <div className="hidden sm:flex flex-col">
              <span className="text-xs font-medium text-[#F7F7F7]">{user.full_name}</span>
              <span className="text-[10px] font-mono text-[#A7A7A7] uppercase">{user.role}</span>
            </div>
            <span className="w-7 h-7 rounded bg-[#262626] border border-[#333333] flex items-center justify-center text-xs font-mono text-[#F7F7F7]">
              {user.full_name ? user.full_name.substring(0, 2).toUpperCase() : 'US'}
            </span>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={logout} className="text-xs font-mono">
          Logout
        </Button>
      </div>
    </header>
  );
};
