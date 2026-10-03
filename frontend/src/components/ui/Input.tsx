import React from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helperText, id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full flex flex-col space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-[#A7A7A7]">
            {label}
          </label>
        )}
        <input
          id={inputId}
          ref={ref}
          className={cn(
            'w-full h-9 px-3 bg-[#1F1F1F] text-[#F7F7F7] border border-[#333333] rounded text-sm placeholder-[#A7A7A7]/50 focus:outline-none focus:border-[#E50039] focus:ring-1 focus:ring-[#E50039] transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            error && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]',
            className
          )}
          {...props}
        />
        {error && <span className="text-xs text-[#EF4444]">{error}</span>}
        {!error && helperText && <span className="text-xs text-[#A7A7A7]">{helperText}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';
