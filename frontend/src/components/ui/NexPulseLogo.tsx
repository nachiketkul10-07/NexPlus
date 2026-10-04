import React from 'react';
import { cn } from '../../lib/utils';

export interface NexPulseLogoProps {
  variant?: 'full' | 'mark' | 'sidebar' | 'hero';
  className?: string;
  showTagline?: boolean;
}

export const NexPulseLogo: React.FC<NexPulseLogoProps> = ({
  variant = 'full',
  className,
  showTagline = true,
}) => {
  // Brand Logo Mark: Stylized 3D red block 'N' with white pulse waveform line
  const logoMark = (
    <svg
      viewBox="0 0 100 100"
      className={cn(
        variant === 'sidebar' ? 'w-8 h-8' : variant === 'hero' ? 'w-20 h-20 sm:w-28 sm:h-28' : 'w-10 h-10',
        'flex-shrink-0 drop-shadow-[0_0_12px_rgba(229,0,57,0.4)]'
      )}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="NexPulse Mark"
    >
      <defs>
        <linearGradient id="nGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#E50039" />
          <stop offset="100%" stopColor="#660019" />
        </linearGradient>
        <linearGradient id="nGrad2" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#FF1A4B" />
          <stop offset="100%" stopColor="#990026" />
        </linearGradient>
        <filter id="redGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Left Vertical Pillar */}
      <path d="M 18,12 L 36,12 L 36,88 L 18,88 Z" fill="url(#nGrad1)" />
      
      {/* Right Vertical Pillar */}
      <path d="M 64,12 L 82,12 L 82,88 L 64,88 Z" fill="url(#nGrad1)" />

      {/* Diagonal Connecting Beam */}
      <path d="M 36,12 L 64,68 L 64,88 L 36,32 Z" fill="url(#nGrad2)" />
      
      {/* Bevel Highlights */}
      <path d="M 18,12 L 36,12 L 27,24 L 18,12 Z" fill="#FF4D73" opacity="0.6" />
      <path d="M 64,12 L 82,12 L 82,24 L 64,12 Z" fill="#FF4D73" opacity="0.6" />

      {/* Red Ambient Glow Filter Overlay */}
      <rect x="15" y="10" width="70" height="80" fill="none" stroke="#E50039" strokeWidth="1" opacity="0.3" filter="url(#redGlow)" />

      {/* Central White Waveform Pulse Line */}
      <path
        d="M 5,50 L 32,50 L 38,32 L 44,68 L 52,24 L 60,60 L 66,50 L 95,50"
        stroke="#FFFFFF"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        className="drop-shadow-[0_0_6px_rgba(255,255,255,0.8)]"
      />
    </svg>
  );

  if (variant === 'mark') {
    return <div className={cn('inline-flex items-center', className)}>{logoMark}</div>;
  }

  if (variant === 'sidebar') {
    return (
      <div className={cn('flex items-center space-x-3', className)}>
        {logoMark}
        <div className="flex flex-col">
          <div className="flex items-center text-sm font-bold font-mono tracking-tight text-[#F7F7F7]">
            <span>Nex</span>
            <span className="text-[#E50039]">Pulse</span>
          </div>
          <span className="text-[9px] text-[#A7A7A7] uppercase tracking-widest font-mono">
            OBSERVE | DETECT | RESPOND
          </span>
        </div>
      </div>
    );
  }

  if (variant === 'hero') {
    return (
      <div className={cn('flex flex-col items-center text-center space-y-4', className)}>
        <div className="relative">
          {logoMark}
        </div>
        <div className="space-y-1">
          <div className="text-4xl sm:text-6xl font-black font-mono tracking-tight text-[#F7F7F7]">
            Nex<span className="text-[#E50039]">Pulse</span>
          </div>
          {showTagline && (
            <div className="text-xs sm:text-sm text-[#A7A7A7] uppercase tracking-[0.3em] font-mono font-medium">
              OBSERVE <span className="text-[#E50039] font-bold">|</span> DETECT <span className="text-[#E50039] font-bold">|</span> RESPOND
            </div>
          )}
        </div>
      </div>
    );
  }

  // Default 'full' variant
  return (
    <div className={cn('inline-flex items-center space-x-3', className)}>
      {logoMark}
      <div className="flex flex-col text-left">
        <div className="text-xl font-extrabold font-mono tracking-tight text-[#F7F7F7]">
          Nex<span className="text-[#E50039]">Pulse</span>
        </div>
        {showTagline && (
          <div className="text-[10px] text-[#A7A7A7] uppercase tracking-[0.2em] font-mono">
            OBSERVE | DETECT | RESPOND
          </div>
        )}
      </div>
    </div>
  );
};
