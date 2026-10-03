import React from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { NexPulseLogo } from '../ui/NexPulseLogo';

export interface NavItem {
  label: string;
  path: string;
  code: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Overview', path: '/app/overview', code: 'OV' },
  { label: 'Services', path: '/app/services', code: 'SV' },
  { label: 'Incidents', path: '/app/incidents', code: 'IN' },
  { label: 'Alerts', path: '/app/alerts', code: 'AL' },
  { label: 'Metrics', path: '/app/metrics', code: 'MT' },
  { label: 'Logs', path: '/app/logs', code: 'LG' },
  { label: 'AI Assistant', path: '/app/ai', code: 'AI' },
  { label: 'Reports', path: '/app/reports', code: 'RP' },
  { label: 'Settings', path: '/app/settings', code: 'ST' },
];

export interface SidebarProps {
  className?: string;
  onNavClick?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ className, onNavClick }) => {
  return (
    <aside className={cn('workspace-sidebar w-64 bg-[#1F1F1F] border-r border-[#333333] flex flex-col justify-between h-full', className)}>
      {/* Brand Header */}
      <div className="p-4 border-b border-[#333333]">
        <NavLink to="/" onClick={onNavClick} className="sidebar-brand block">
          <NexPulseLogo variant="sidebar" />
        </NavLink>
      </div>

      {/* Primary Navigation */}
      <nav aria-label="System views" className="p-3 space-y-1 flex-1 overflow-y-auto">
        <div className="px-3 py-2 text-[10px] font-mono font-semibold text-[#A7A7A7] uppercase tracking-wider">
          System Views
        </div>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onNavClick}
            className={({ isActive }) =>
              cn(
                'sidebar-nav-item flex items-center space-x-3 px-3 py-2 rounded text-xs font-medium',
                isActive
                  ? 'is-active bg-[#E50039]/15 text-[#F7F7F7] font-semibold border border-[#E50039]/40'
                  : 'text-[#A7A7A7] hover:text-[#F7F7F7] hover:bg-[#262626]'
              )
            }
          >
            <span className="sidebar-nav-code w-5 font-mono text-[10px] text-[#A7A7A7]">{item.code}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-[#333333] text-[11px] font-mono text-[#A7A7A7]">
        <div className="flex items-center justify-between">
          <span>ENV: PROD</span>
          <span className="text-[#10B981]">v0.6.0</span>
        </div>
      </div>
    </aside>
  );
};

