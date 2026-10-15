import React from 'react';
import { getServiceSignalLabel, getServiceSignalState } from '../../lib/utils';

interface ServiceSignalIndicatorProps {
  isActive: boolean | undefined;
  lastSeenAt: string | null | undefined;
  className?: string;
}

export const ServiceSignalIndicator: React.FC<ServiceSignalIndicatorProps> = ({
  isActive,
  lastSeenAt,
  className = '',
}) => {
  const state = getServiceSignalState(isActive, lastSeenAt);
  const tone = state === 'receiving'
    ? 'text-[#10B981]'
    : state === 'quiet'
      ? 'text-[#F59E0B]'
      : state === 'inactive'
        ? 'text-[#EF4444]'
        : 'text-[#A7A7A7]';

  const title = state === 'quiet'
    ? 'No signal in the last five minutes. This can be normal for idle serverless or Streamlit apps.'
    : undefined;

  return (
    <span className={`inline-flex items-center gap-2 text-xs font-medium ${tone} ${className}`} title={title}>
      <span className={`h-2 w-2 shrink-0 rounded-full ${state === 'receiving' ? 'bg-[#10B981]' : state === 'quiet' ? 'bg-[#F59E0B]' : state === 'inactive' ? 'bg-[#EF4444]' : 'bg-[#A7A7A7]'}`} aria-hidden="true" />
      {getServiceSignalLabel(state)}
    </span>
  );
};
