import React from 'react';
import { cn } from '../../lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading = false, children, disabled, ...props }, ref) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#E50039] focus:ring-offset-2 focus:ring-offset-[#191919] disabled:opacity-50 disabled:pointer-events-none rounded';

    const variants = {
      primary: 'bg-[#E50039] text-white hover:bg-[#660019] active:bg-[#660019]',
      secondary: 'bg-[#262626] text-[#F7F7F7] border border-[#333333] hover:bg-[#333333] active:bg-[#333333]',
      outline: 'bg-transparent text-[#F7F7F7] border border-[#333333] hover:bg-[#262626] active:bg-[#262626]',
      ghost: 'bg-transparent text-[#A7A7A7] hover:text-[#F7F7F7] hover:bg-[#262626]',
      danger: 'bg-[#EF4444] text-white hover:bg-[#b91c1c] active:bg-[#991b1b]',
    };

    const sizes = {
      sm: 'h-8 px-3 text-xs',
      md: 'h-9 px-4 text-sm',
      lg: 'h-11 px-6 text-base',
    };

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && (
          <span className="mr-2 inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin motion-reduce:animate-none" />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
