import React from 'react';
import { cn } from '../../lib/utils';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Skeleton: React.FC<SkeletonProps> = ({ className, ...props }) => {
  return (
    <div
      className={cn(
        'bg-[#262626] animate-pulse rounded motion-reduce:animate-none border border-[#333333]/50',
        className
      )}
      {...props}
    />
  );
};
