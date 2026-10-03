import React, { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { NexPulseLogo } from '../ui/NexPulseLogo';

export const AppShell: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [routeTransitioning, setRouteTransitioning] = useState<boolean>(false);
  const location = useLocation();
  const reducedMotion = useReducedMotion();
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    if (previousPath.current === location.pathname) return;

    previousPath.current = location.pathname;
    setRouteTransitioning(true);
    const timeout = window.setTimeout(() => setRouteTransitioning(false), reducedMotion ? 140 : 720);
    return () => window.clearTimeout(timeout);
  }, [location.pathname, reducedMotion]);

  return (
    <div className="min-h-screen bg-[#191919] text-[#F7F7F7] flex flex-col md:flex-row antialiased font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:block w-64 flex-shrink-0 h-screen sticky top-0">
        <Sidebar />
      </div>

      {/* Mobile Sidebar Overlay */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div className="fixed inset-0 z-50 flex md:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reducedMotion ? 0.01 : 0.2 }}>
            <motion.div
              className="fixed inset-0 bg-black/80"
              onClick={() => setMobileMenuOpen(false)}
              aria-hidden="true"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reducedMotion ? 0.01 : 0.2 }}
            />
            <motion.div
              className="relative w-64 max-w-xs bg-[#1F1F1F] h-full z-10 flex flex-col border-r border-[#333333]"
              initial={{ x: -28, opacity: 0.8 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -28, opacity: 0.8 }}
              transition={{ duration: reducedMotion ? 0.01 : 0.24, ease: 'easeOut' }}
            >
              <Sidebar onNavClick={() => setMobileMenuOpen(false)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content Workspace */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        <TopBar onToggleMobileMenu={() => setMobileMenuOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <motion.div key={location.pathname} initial={{ opacity: 0, y: reducedMotion ? 0 : 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reducedMotion ? 0.15 : 0.28, ease: 'easeOut' }}>
            <Outlet />
          </motion.div>
        </main>
      </div>

      <AnimatePresence>
        {routeTransitioning && (
          <motion.div
            key={location.pathname}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-[#101114]/90 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reducedMotion ? 0.08 : 0.16 }}
            role="status"
            aria-label="Loading page"
          >
            <div className="flex flex-col items-center gap-4">
              <motion.div
                className="rounded-2xl border border-[#E50039]/30 bg-[#1F1F1F]/90 p-4 shadow-[0_0_42px_rgba(229,0,57,0.22)]"
                animate={{ rotate: reducedMotion ? 0 : 360, scale: [1, 1.04, 1] }}
                transition={{
                  rotate: { duration: reducedMotion ? 0 : 0.72, ease: 'linear', repeat: reducedMotion ? 0 : Infinity },
                  scale: { duration: reducedMotion ? 0 : 0.9, repeat: reducedMotion ? 0 : Infinity, ease: 'easeInOut' },
                }}
              >
                <NexPulseLogo variant="mark" className="[&>svg]:h-14 [&>svg]:w-14" />
              </motion.div>
              <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-white/65">Loading view</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
