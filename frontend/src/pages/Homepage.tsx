import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { NexPulseLogo } from '../components/ui/NexPulseLogo';
import { Button } from '../components/ui/Button';
import { useAuth } from '../app/AuthContext';

const rise = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] } },
};

const stages = [
  ['01', 'Application', 'Requests and service signals'],
  ['02', 'Telemetry', 'Events, metrics, and logs'],
  ['03', 'NexPulse', 'Correlate evidence in context'],
  ['04', 'Response', 'Investigate and resolve'],
];

export const Homepage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const reducedMotion = useReducedMotion();
  const registrationEnabled = import.meta.env.DEV || import.meta.env.VITE_PUBLIC_REGISTRATION_ENABLED === 'true';
  const launch = () => navigate(user ? '/app/overview' : '/login');

  return (
    <div className="landing-shell min-h-screen bg-[#191919] text-[#F7F7F7] selection:bg-[#E50039] selection:text-white">
      <header className="landing-nav mx-auto flex h-[76px] max-w-[1360px] items-center justify-between px-5 sm:px-8">
        <NexPulseLogo variant="full" />
        <nav aria-label="Main navigation" className="flex items-center gap-3">
          <button className="landing-nav-link" onClick={() => document.getElementById('platform')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' })}>Platform</button>
          {user ? <Button size="sm" onClick={launch}>Open workspace</Button> : <>
            <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>Sign in</Button>
            {registrationEnabled && <Button size="sm" onClick={() => navigate('/register')}>Create account</Button>}
          </>}
        </nav>
      </header>

      <main>
        <section className="landing-hero relative mx-auto flex min-h-[690px] max-w-[1360px] items-center overflow-hidden px-5 pb-20 pt-16 sm:px-8 lg:min-h-[760px]">
          <div className="signal-stage" aria-hidden="true">
            <div className="signal-ring signal-ring-a" />
            <div className="signal-ring signal-ring-b" />
            <div className="signal-core"><span /></div>
            <svg className="signal-routes" viewBox="0 0 900 560" fill="none" preserveAspectRatio="xMidYMid meet">
              <path d="M450 280H690V152H835" /><path d="M450 280H224V125H72" /><path d="M450 280V446H735" /><path d="M450 280V76H552" />
              <circle cx="690" cy="152" r="4"/><circle cx="224" cy="125" r="4"/><circle cx="735" cy="446" r="4"/><circle cx="552" cy="76" r="4"/>
              <path className="signal-trace" d="M450 280H690V152H835M450 280H224V125H72M450 280V446H735M450 280V76H552" />
            </svg>
            <div className="signal-readout readout-a"><i />INGESTION <b>LIVE</b><span>HTTP / METRICS / LOGS</span></div>
            <div className="signal-readout readout-b"><i />SERVICE HEALTH <b>OBSERVED</b><span>LAST SIGNAL · JUST NOW</span></div>
            <div className="signal-readout readout-c"><i />INCIDENT FLOW <b>READY</b><span>EVIDENCE → INVESTIGATION</span></div>
          </div>

          <motion.div className="landing-copy relative z-10 max-w-[700px]" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: reducedMotion ? 0 : 0.18, delayChildren: reducedMotion ? 0 : 0.12 } } }}>
            <motion.div variants={rise} className="mb-9"><NexPulseLogo variant="hero" showTagline={false} /></motion.div>
            <motion.p variants={rise} className="landing-eyebrow"><span /> OBSERVE <i>/</i> DETECT <i>/</i> RESPOND</motion.p>
            <motion.h1 variants={rise} className="landing-title">Know when your<br /><span>systems lose the signal.</span></motion.h1>
            <motion.p variants={rise} className="landing-lede">A focused observability workspace for service telemetry, actionable alerts, and evidence-led incident response.</motion.p>
            <motion.div variants={rise} className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button size="lg" onClick={launch}>{user ? 'Enter workspace' : 'Open NexPulse'} <span aria-hidden="true">↗</span></Button>
              <Button variant="secondary" size="lg" onClick={() => document.getElementById('platform')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' })}>Explore the platform</Button>
            </motion.div>
            <motion.p variants={rise} className="landing-footnote">SERVICE HEALTH <span>·</span> TELEMETRY <span>·</span> INCIDENT RESPONSE</motion.p>
          </motion.div>
        </section>

        <section id="platform" className="mx-auto max-w-[1360px] px-5 pb-24 pt-20 sm:px-8">
          <motion.div className="landing-section-head" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.35 }} variants={rise}>
            <p className="landing-eyebrow">FROM SIGNAL TO RESPONSE</p>
            <h2>Operational context, <span>without the noise.</span></h2>
            <p>Follow a request from the service that emitted it to the evidence that helps your team act.</p>
          </motion.div>
          <div className="flow-track" aria-label="Application to incident response flow">
            {stages.map(([number, title, description], index) => <motion.div key={number} className="flow-step" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.4 }} variants={rise} transition={{ delay: index * 0.08 }}>
              <span className="flow-index">{number}</span><h3>{title}</h3><p>{description}</p>
              {index < stages.length - 1 && <span className="flow-connector" aria-hidden="true">/</span>}
            </motion.div>)}
          </div>
        </section>

        <section className="landing-capabilities mx-auto grid max-w-[1360px] gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[0.8fr_1.2fr]">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.35 }} variants={rise}>
            <p className="landing-eyebrow">BUILT FOR THE MOMENT THAT MATTERS</p>
            <h2>See the system.<br /><span>Understand the incident.</span></h2>
            <p className="landing-body">NexPulse brings service health, request activity, alert state, and investigation history into one practical operating view.</p>
            <Button variant="ghost" size="sm" onClick={launch}>Go to the workspace <span aria-hidden="true">↗</span></Button>
          </motion.div>
          <div className="capability-list">
            {[
              ['01', 'Service observability', 'Track health and inspect the request signals behind a change.'],
              ['02', 'Alerting with context', 'Evaluate thresholds against persisted telemetry and follow active state.'],
              ['03', 'Evidence-led response', 'Keep incident updates, supporting signals, and next checks together.'],
            ].map(([n, title, text], index) => <motion.article className="capability-row" key={n} initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.5 }} variants={rise} transition={{ delay: index * 0.1 }}>
              <span>{n}</span><div><h3>{title}</h3><p>{text}</p></div><b aria-hidden="true">↗</b>
            </motion.article>)}
          </div>
        </section>

        <section className="landing-end mx-auto max-w-[1360px] px-5 py-20 sm:px-8">
          <motion.div className="landing-end-panel" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.35 }} variants={rise}>
            <p className="landing-eyebrow">NEXPULSE · OBSERVE / DETECT / RESPOND</p>
            <h2>Make the next incident<br /><span>easier to understand.</span></h2>
            <Button size="lg" onClick={launch}>Enter NexPulse Workspace <span aria-hidden="true">↗</span></Button>
          </motion.div>
        </section>
      </main>

      <footer className="landing-footer mx-auto flex max-w-[1360px] flex-col items-start justify-between gap-4 px-5 py-7 sm:flex-row sm:items-center sm:px-8">
        <NexPulseLogo variant="sidebar" /><span>Operational clarity for the systems you run.</span><span>© NexPulse</span>
      </footer>
    </div>
  );
};
