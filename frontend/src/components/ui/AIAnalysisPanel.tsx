import React, { useState, useEffect, useCallback } from 'react';
import { AIAnalysisResponse } from '../../types';
import { generateAIAnalysisApi, getLatestAIAnalysisApi } from '../../services/incidents';
import { Badge } from './Badge';
import { Button } from './Button';
import { Skeleton } from './Skeleton';
import { safeExtractErrorMessage } from '../../lib/utils';

export interface AIAnalysisPanelProps {
  incidentId: string;
}

const sourceLabel = (source: string) => source.replace(/_/g, ' ');

export const AIAnalysisPanel: React.FC<AIAnalysisPanelProps> = ({ incidentId }) => {
  const [analysis, setAnalysis] = useState<AIAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getLatestAIAnalysisApi(incidentId);
      setAnalysis(data);
    } catch {
      try {
        const fresh = await generateAIAnalysisApi(incidentId, false);
        setAnalysis(fresh);
      } catch (err) {
        setError(safeExtractErrorMessage(err));
      }
    } finally {
      setIsLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis]);

  const handleRefresh = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const fresh = await generateAIAnalysisApi(incidentId, true);
      setAnalysis(fresh);
    } catch (err) {
      setError(safeExtractErrorMessage(err));
    } finally {
      setIsGenerating(false);
    }
  };

  const isLive = analysis?.status === 'generated';
  const modelLabel = analysis?.model_name?.replace(/[-_]/g, ' ') || analysis?.provider || 'Configured provider';

  const getConfidenceBadge = (confidence: string) => {
    const styles = confidence === 'high'
      ? 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20'
      : confidence === 'medium'
        ? 'bg-amber-400/10 text-amber-300 border-amber-400/20'
        : 'bg-white/[0.06] text-white/55 border-white/10';
    return <span className={`shrink-0 rounded-full border px-2 py-1 text-[9px] font-mono uppercase tracking-wider ${styles}`}>{confidence} confidence</span>;
  };

  if (isLoading) {
    return (
      <div className="space-y-4 rounded-xl border border-white/[0.08] bg-[#1E2025] p-5">
        <div className="flex items-center justify-between"><Skeleton className="h-5 w-48" /><Skeleton className="h-7 w-32" /></div>
        <Skeleton className="h-28 w-full" />
        <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-40 w-full" /><Skeleton className="h-40 w-full" /></div>
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-xl border border-white/[0.08] bg-[#1E2025]">
      <header className="flex flex-col gap-4 border-b border-white/[0.07] p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#E50039]/20 bg-[#E50039]/[0.08] text-[#FF5279]" aria-hidden="true">✳</div>
          <div>
            <h2 className="text-sm font-semibold text-white">Incident analysis</h2>
            <p className="mt-0.5 text-[11px] text-white/40">Evidence, hypotheses, and operator next steps</p>
          </div>
          {analysis && (isLive ? <Badge variant="info">LIVE AI</Badge> : analysis.status === 'fallback' ? <Badge variant="warning">EVIDENCE FALLBACK</Badge> : <Badge variant="neutral">UNAVAILABLE</Badge>)}
        </div>
        <Button variant="secondary" size="sm" isLoading={isGenerating} onClick={handleRefresh} className="text-xs">
          {analysis ? 'Refresh analysis' : 'Generate analysis'}
        </Button>
      </header>

      {error && (
        <div className="m-4 flex flex-col gap-3 rounded-lg border border-rose-400/20 bg-rose-400/[0.07] p-4 sm:flex-row sm:items-center sm:justify-between sm:m-5">
          <div><p className="text-xs font-semibold text-rose-200">Analysis request failed</p><p className="mt-1 text-xs text-rose-100/60">{error}</p></div>
          <Button variant="secondary" size="sm" isLoading={isGenerating} onClick={handleRefresh}>Try again</Button>
        </div>
      )}

      {analysis && (
        <div className="space-y-5 p-4 sm:p-5">
          <div className={`rounded-xl border p-4 sm:p-5 ${isLive ? 'border-sky-400/15 bg-[linear-gradient(110deg,rgba(56,189,248,0.07),rgba(23,24,29,0.7))]' : 'border-amber-400/15 bg-[linear-gradient(110deg,rgba(251,191,36,0.07),rgba(23,24,29,0.7))]'}`}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-white/45">Assessment summary</span>
              <span className="text-[10px] text-white/35">{isLive ? `Generated with ${modelLabel}` : 'Generated from stored telemetry evidence'} · {new Date(analysis.created_at).toLocaleString()}</span>
            </div>
            <p className="text-sm leading-7 text-white/85">{analysis.summary}</p>
          </div>

          {!isLive && (
            <div className="flex gap-3 rounded-lg border border-amber-300/15 bg-amber-300/[0.05] p-3.5">
              <span className="mt-0.5 text-amber-300" aria-hidden="true">●</span>
              <div>
                <p className="text-xs font-semibold text-amber-100">Evidence fallback is active</p>
                <p className="mt-1 text-xs leading-5 text-amber-100/60">{analysis.limitations_note} Add a Groq API key to the backend environment and restart the API to enable live model analysis. The current result remains useful, traceable telemetry guidance.</p>
              </div>
            </div>
          )}

          <div className="grid gap-5 xl:grid-cols-2">
            <section className="space-y-3">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-[10px] font-mono uppercase tracking-[0.15em] text-white/50">Observed evidence</h3>
                <span className="text-[10px] text-white/35">{analysis.evidence?.length ?? 0} signals</span>
              </div>
              {analysis.evidence?.length ? (
                <div className="space-y-2">
                  {analysis.evidence.map((item, index) => (
                    <article key={`${item.source_type}-${item.source_reference}-${index}`} className="rounded-lg border border-white/[0.07] bg-[#17181D] p-3.5">
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <span className="rounded-md bg-[#E50039]/[0.09] px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#FF6A8B]">{sourceLabel(item.source_type)}</span>
                        {item.source_reference && <span className="max-w-full break-all text-[10px] text-white/35">{item.source_reference}</span>}
                      </div>
                      <p className="text-xs leading-5 text-white/75">{item.observation}</p>
                    </article>
                  ))}
                </div>
              ) : <p className="rounded-lg border border-dashed border-white/10 p-4 text-xs text-white/40">No telemetry evidence was attached to this analysis.</p>}
            </section>

            <section className="space-y-5">
              <div className="space-y-3">
                <h3 className="text-[10px] font-mono uppercase tracking-[0.15em] text-white/50">Possible causes · hypotheses</h3>
                {analysis.possible_causes?.length ? analysis.possible_causes.map((cause, index) => (
                  <article key={`${cause.statement}-${index}`} className="rounded-lg border border-white/[0.07] bg-[#17181D] p-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs leading-5 text-white/80">{cause.statement}</p>
                      {getConfidenceBadge(cause.confidence)}
                    </div>
                    {cause.supporting_evidence?.length > 0 && (
                      <div className="mt-3 border-t border-white/[0.06] pt-2.5">
                        <div className="mb-1 text-[9px] font-mono uppercase tracking-wider text-white/35">Supporting signals</div>
                        <ul className="space-y-1">{cause.supporting_evidence.map((evidence, evidenceIndex) => <li key={evidenceIndex} className="flex gap-2 text-[11px] leading-5 text-white/55"><span className="text-[#FF5279]">↳</span>{evidence}</li>)}</ul>
                      </div>
                    )}
                  </article>
                )) : <p className="text-xs text-white/40">No hypotheses were returned.</p>}
              </div>

              <div className="space-y-3">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-[10px] font-mono uppercase tracking-[0.15em] text-white/50">Recommended next checks</h3>
                  <span className="text-[10px] text-white/35">Operator reviewed</span>
                </div>
                {analysis.next_checks?.length ? (
                  <ol className="space-y-2">
                    {analysis.next_checks.map((check, index) => (
                      <li key={index} className="flex gap-3 rounded-lg border border-white/[0.06] bg-[#17181D] p-3">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[10px] font-mono text-white/55">{index + 1}</span>
                        <span className="text-xs leading-5 text-white/70">{check}</span>
                      </li>
                    ))}
                  </ol>
                ) : <p className="text-xs text-white/40">No follow-up checks were returned.</p>}
              </div>
            </section>
          </div>

          <footer className="rounded-lg border border-white/[0.06] bg-[#17181D] px-3.5 py-3 text-[11px] leading-5 text-white/45">
            <span className="mr-1.5 font-semibold uppercase tracking-wider text-white/65">Advisory only</span>
            NexPulse does not execute remediation. Validate hypotheses against your own runbooks and live service state. {isLive && analysis.limitations_note}
          </footer>
        </div>
      )}
    </section>
  );
};
