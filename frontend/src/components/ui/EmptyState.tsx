import React from 'react';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  className,
}) => {
  return (
    <div
      className={cn(
        'w-full bg-[#1F1F1F] border border-[#333333] rounded p-8 flex flex-col items-center justify-center text-center space-y-3',
        className
      )}
    >
      <div className="w-10 h-10 rounded border border-[#333333] bg-[#262626] flex items-center justify-center text-[#A7A7A7] font-mono text-sm font-bold">
        NO_DATA
      </div>
      <div className="space-y-1 max-w-md">
        <h3 className="text-sm font-medium text-[#F7F7F7]">{title}</h3>
        <p className="text-xs text-[#A7A7A7] leading-relaxed">{description}</p>
      </div>
      {actionLabel && onAction && (
        <div className="pt-2">
          <Button size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      )}
    </div>
  );
};
