import React from 'react';
import { cn } from '../../lib/utils';
import { ServiceStatus } from '../../types';

export interface StatusIndicatorProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: ServiceStatus | 'unknown';
  showLabel?: boolean;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  showLabel = true,
  className,
  ...props
}) => {
  const statusColors: Record<string, string> = {
    healthy: 'bg-[#10B981]',
    degraded: 'bg-[#F59E0B]',
    critical: 'bg-[#EF4444]',
    offline: 'bg-[#A7A7A7]',
    unknown: 'bg-[#A7A7A7]',
  };

  const statusLabels: Record<string, string> = {
    healthy: 'Healthy',
    degraded: 'Degraded',
    critical: 'Critical',
    offline: 'Offline',
    unknown: 'Unknown',
  };

  const dotColor = statusColors[status] || statusColors.unknown;
  const label = statusLabels[status] || statusLabels.unknown;

  return (
    <span className={cn('inline-flex items-center space-x-2 text-xs font-medium', className)} {...props}>
      <span className={cn('w-2 h-2 rounded-full flex-shrink-0', dotColor)} />
      {showLabel && <span className="text-[#F7F7F7] capitalize">{label}</span>}
    </span>
  );
};
