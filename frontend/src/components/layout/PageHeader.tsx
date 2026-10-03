import React from 'react';

export interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, action }) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-[#333333] mb-6 gap-3">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-[#F7F7F7] font-mono">{title}</h1>
        {description && <p className="text-xs text-[#A7A7A7] mt-1 leading-relaxed">{description}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
};
