import React from 'react';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export interface ErrorStateProps {
  title?: string;
  message: string;
  statusCode?: number;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Request Failed',
  message,
  statusCode,
  onRetry,
  className,
}) => {
  return (
    <div
      className={cn(
        'w-full bg-[#1F1F1F] border border-[#EF4444]/40 rounded p-6 flex flex-col items-center justify-center text-center space-y-3',
        className
      )}
    >
      <div className="w-10 h-10 rounded border border-[#EF4444]/30 bg-[#EF4444]/10 flex items-center justify-center text-[#EF4444] font-mono text-xs font-bold">
        {statusCode || 'ERR'}
      </div>
      <div className="space-y-1 max-w-md">
        <h3 className="text-sm font-medium text-[#F7F7F7]">{title}</h3>
        <p className="text-xs text-[#A7A7A7] leading-relaxed">{message}</p>
      </div>
      {onRetry && (
        <div className="pt-2">
          <Button variant="outline" size="sm" onClick={onRetry}>
            Retry Request
          </Button>
        </div>
      )}
    </div>
  );
};
