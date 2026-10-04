import { useEffect, useRef, useState } from 'react';
import type { RunAnalysis } from '../analysis/types';
import {
  deriveUiState,
  formatLogLine,
  loadLogOpenPref,
  saveLogOpenPref,
  secondsAgo,
  type AnalyzerJobProgress,
} from '../analysis/analyzerJobProgress';
import { SignalContextPanel } from './SignalContextPanel';

function show(v: any) {
  if (v == null || v === 'NOT AVAILABLE') return 'NOT AVAILABLE';
  if (typeof v === 'number' && Number.isFinite(v)) return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function fmtInt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(Number(n))) return '—';
  return Math.trunc(Number(n)).toLocaleString('en-US');
}

export type AnalysisSourceMode = 'current' | 'saved';

export type RunCatalogEntry = {
  run_id: string;
  final_tick?: number | null;
  seed?: number | null;
  runtime_type?: string | null;
  agent_count?: number | null;
  has_scientific_timeline?: boolean;
  scientific_tick_range?: [number | null, number | null] | null;
  termination_reason?: string | null;
};

export type AnalysisProgressState = AnalyzerJobProgress & {
  job_id?: string;
  state?: string;
  phase?: string;
  phase_index?: number | null;
  phase_count?: number | null;
  completed_units?: number | null;
  total_units?: number | null;
  percent?: number | null;
  status_text?: string;
  terminal?: boolean;
  error_code?: string | null;
  error_message?: string | null;
};

export function AnalyzeResultsPanel({
  analysis,
  analyzing,
  analysisProgress,
  analysisProgressDetail,
  analysisError,
  analysisSource,
  onAnalysisSourceChange,
  savedRuns,
  selectedRunId,
  onSelectRunId,
  onRefreshRuns,
  onAnalyze,
  onCancelAnalysis,
  onCopy,
  onDownload,
  onCopyReport,
  onSaveMarkdown,
  onSaveJson,
  onInspectTick,
}: {
  analysis: RunAnalysis | null;
  analyzing?: boolean;
  analysisProgress?: string;
  analysisProgressDetail?: AnalysisProgressState | null;
  analysisError?: string | null;
  analysisSource: AnalysisSourceMode;
  onAnalysisSourceChange: (s: AnalysisSourceMode) => void;
  savedRuns: RunCatalogEntry[];
  selectedRunId: string | null;
  onSelectRunId: (id: string | null) => void;
  onRefreshRuns: () => void;
  onAnalyze: () => void;
  onCancelAnalysis?: () => void;
  onCopy: () => void;
  onDownload: () => void;
  onCopyReport?: () => void;
  onSaveMarkdown?: () => void;
  onSaveJson?: () => void;
  onInspectTick: (tick: number) => void;
}) {
  const [showPicker, setShowPicker] = useState(false);
  const [logOpen, setLogOpen] = useState(() => loadLogOpenPref());
  const [nowMs, setNowMs] = useState(() => Date.now());
  const logRef = useRef<HTMLPreElement | null>(null);
  const stickBottomRef = useRef(true);
  const meta = analysis?.evidence_meta;
  const id = analysis?.identity;
  const life = analysis?.lifecycle;
  const exportReady = Boolean(analysis && !analyzing);
  const sourceLabel = analysisSource === 'saved'
    ? `SAVED RUN${selectedRunId ? `: ${selectedRunId}` : ''}`
    : 'CURRENT RUN';
  const prog = analysisProgressDetail || null;
  const pct = prog?.percent;
  const determinate = pct != null && Number.isFinite(Number(pct));
  const ui = deriveUiState(prog, nowMs);
  const processed = prog?.phase_processed ?? prog?.completed_units ?? prog?.overall_processed ?? null;
  const total = prog?.phase_total ?? prog?.total_units ?? prog?.overall_total ?? null;
  const unitLabel = prog?.unit_label || 'ticks';
  const phaseIdx = prog?.phase_index != null ? Number(prog.phase_index) + 1 : null;
  const phaseCount = prog?.phase_count != null ? Number(prog.phase_count) : null;
  const hbAge = secondsAgo(prog?.worker_heartbeat_at || prog?.heartbeat_at || prog?.updated_at, nowMs);
  const elapsed = prog?.elapsed_seconds ?? prog?.elapsed_s ?? null;
  const rate = prog?.records_per_second;
  const snapTick = prog?.snapshot_terminal_tick;
  const logEntries = Array.isArray(prog?.recent_log) ? prog!.recent_log! : [];
  const canCancel = Boolean(analyzing && onCancelAnalysis && !prog?.terminal);

  useEffect(() => {
    if (!analyzing) return;
    const t = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [analyzing]);

  useEffect(() => {
    saveLogOpenPref(logOpen);
  }, [logOpen]);

  useEffect(() => {
    if (!logOpen || !logRef.current || !stickBottomRef.current) return;
    logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logOpen, logEntries.length, analyzing]);

  return <div className="dashboard-grid">
    <section className="panel science-card wide" data-testid="analyze-results-root">
      <h3>ANALYZE RESULTS</h3>
      <div className="subtle" style={{ marginBottom: 8 }}>
        Analysis is read-only. It does not pause, advance, or modify the scientific runtime.
      </div>
      <div className="metric" data-testid="analyze-source-identity">
        <span>Active source</span>
        <strong>{sourceLabel}</strong>
      </div>
      <fieldset className="analyze-source">
        <legend style={{ padding: '0 6px' }}>Analysis source</legend>
        <label style={{ display: 'block', marginBottom: 8 }}>
          <input
            type="radio"
            name="analysis-source"
            checked={analysisSource === 'current'}
            onChange={() => onAnalysisSourceChange('current')}
          />{' '}
          <strong>Current running experiment</strong>
          <div className="subtle" style={{ marginLeft: 22 }}>
            Analyze all scientific evidence recorded so far.
            Runtime continues running and is not modified.
          </div>
        </label>
        <label style={{ display: 'block', marginBottom: 8 }}>
          <input
            type="radio"
            name="analysis-source"
            checked={analysisSource === 'saved'}
            onChange={() => onAnalysisSourceChange('saved')}
          />{' '}
          <strong>Saved experiment</strong>
          <div className="subtle" style={{ marginLeft: 22 }}>
            Select an existing run and analyze its recorded evidence.
          </div>
        </label>
        {analysisSource === 'saved' ? (
          <div style={{ marginLeft: 22, marginBottom: 8 }}>
            <div className="toolbar-row">
              <button type="button" onClick={() => { onRefreshRuns(); setShowPicker((v) => !v); }}>
                {selectedRunId ? `Selected: ${selectedRunId}` : 'Select Run…'}
              </button>
              {selectedRunId ? (
                <button type="button" onClick={() => onSelectRunId(null)}>Clear</button>
              ) : null}
            </div>
            {showPicker ? (
              <div className="science-card" style={{ marginTop: 8, maxHeight: 220, overflow: 'auto', padding: 8 }}>
                {savedRuns.length === 0 ? (
                  <div className="na">No saved psyweb runs found.</div>
                ) : savedRuns.map((r) => (
                  <button
                    key={r.run_id}
                    type="button"
                    className="edge-row"
                    style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 4 }}
                    onClick={() => { onSelectRunId(r.run_id); setShowPicker(false); }}
                  >
                    <b>{r.run_id}</b>
                    <div className="subtle">
                      t{show(r.final_tick)} · seed {show(r.seed)} · {r.runtime_type || '—'} · agents {show(r.agent_count)}
                      {' · '}
                      scientific: {r.has_scientific_timeline ? `YES ${r.scientific_tick_range?.[0]}–${r.scientific_tick_range?.[1]}` : 'NO (legacy PARTIAL)'}
                    </div>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="toolbar-row" style={{ marginTop: 8 }}>
          <button
            className="active"
            type="button"
            disabled={analyzing || (analysisSource === 'saved' && !selectedRunId)}
            onClick={onAnalyze}
            data-testid="analyzer-run"
          >
            {analyzing ? (analysisProgress || 'Analyzing…') : 'Analyze'}
          </button>
          {canCancel ? (
            <button
              type="button"
              onClick={() => onCancelAnalysis?.()}
              data-testid="analyzer-cancel"
              aria-label="Cancel analysis"
            >
              Cancel analysis
            </button>
          ) : null}
        </div>
      </fieldset>

      {analyzing || (prog && !prog.terminal && prog.job_id) ? (
        <div className="inspecting-banner" style={{ marginTop: 12 }} data-testid="analyzer-status-running">
          <strong data-testid="analyzer-state-banner">{ui.banner}</strong>
          <span className="badge">{prog?.phase_label || prog?.phase || analysisProgress || '…'}</span>
          {phaseIdx != null && phaseCount != null ? (
            <span className="badge" data-testid="analyzer-phase-count">{phaseIdx} / {phaseCount}</span>
          ) : null}
          <div
            data-testid="analyzer-progress"
            style={{ marginTop: 8 }}
            aria-live="polite"
            aria-atomic="true"
          >
            <div className="subtle" data-testid="analyzer-progress-units">
              {processed != null
                ? `${fmtInt(processed)}${total != null ? ` / ${fmtInt(total)}` : ''} ${unitLabel}`
                : (prog?.status_text || analysisProgress || 'Working…')}
              {prog?.current_operation ? ` · ${prog.current_operation}` : ''}
            </div>
            {determinate ? (
              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Number(pct)}
                aria-label="Analyzer progress"
                data-testid="analyzer-progress-bar"
                style={{
                  marginTop: 6,
                  height: 8,
                  background: 'var(--border, #444)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div style={{ width: `${Math.max(0, Math.min(100, Number(pct)))}%`, height: '100%', background: 'var(--accent, #6af)' }} />
              </div>
            ) : (
              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Analyzer progress indeterminate"
                data-testid="analyzer-progress-bar-indeterminate"
                style={{
                  marginTop: 6,
                  height: 8,
                  background: 'var(--border, #444)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div className="subtle" style={{ padding: '0 4px', fontSize: 10 }}>indeterminate</div>
              </div>
            )}
            <div className="subtle" style={{ marginTop: 6 }} data-testid="analyzer-heartbeat">
              {elapsed != null ? `Elapsed ${Number(elapsed).toFixed(1)} s` : 'Elapsed —'}
              {' · '}
              {hbAge != null ? `Heartbeat ${hbAge} s ago` : 'Heartbeat —'}
              {rate != null && Number(rate) > 0 ? ` · ${Number(rate).toFixed(1)} ${unitLabel}/s` : ''}
            </div>
            <div className="subtle" data-testid="analyzer-snapshot-bound">
              {snapTick != null
                ? `Analyzing frozen snapshot through tick ${fmtInt(snapTick)}`
                : 'Snapshot boundary pending…'}
              {ui.healthNote ? ` · ${ui.healthNote}` : ''}
            </div>
            <div style={{ marginTop: 8 }}>
              <button
                type="button"
                aria-expanded={logOpen}
                aria-controls="analyzer-compact-log"
                data-testid="analyzer-log-toggle"
                onClick={() => setLogOpen((v) => !v)}
              >
                Analysis log
              </button>
              {logOpen ? (
                <pre
                  id="analyzer-compact-log"
                  ref={logRef}
                  role="log"
                  aria-label="Analysis operational log"
                  data-testid="analyzer-compact-log"
                  onScroll={(e) => {
                    const el = e.currentTarget;
                    stickBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
                  }}
                  style={{
                    marginTop: 6,
                    maxHeight: '10.5em',
                    overflow: 'auto',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                    fontSize: 11,
                    lineHeight: 1.35,
                    padding: 8,
                    background: 'rgba(0,0,0,0.25)',
                    border: '1px solid var(--border, #444)',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {logEntries.length
                    ? logEntries.map((e) => formatLogLine(e)).join('\n')
                    : '(no operational log entries yet)'}
                </pre>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {analysisError && !analyzing ? (
        <div className="na" style={{ marginTop: 12 }} data-testid="analyzer-status-failed" role="alert">
          <strong>ANALYSIS: FAILED</strong>
          <div style={{ marginTop: 6 }}>{analysisError}</div>
          <div className="subtle" style={{ marginTop: 6 }}>
            Source remains {sourceLabel}. Retry Analyze after inspecting the error. Export is disabled until a completed result exists.
          </div>
        </div>
      ) : null}

      {!analysis && !analyzing && !analysisError ? (
        <div className="na" style={{ marginTop: 12 }} data-testid="analyzer-status-idle">
          ANALYSIS: IDLE — choose a source and press Analyze (or open this tab during a live run for automatic buffer view).
        </div>
      ) : null}

      {analysis ? (
        <>
          <div className="inspecting-banner" style={{ marginTop: 12 }} data-testid="analyzer-status-complete">
            <strong>{life?.banner || `ANALYSIS: ${id?.analysis_mode}`}</strong>
            <span className="badge">{life?.coverage || meta?.coverage || '—'}</span>
            <span className="badge">{meta?.source === 'saved' || analysisSource === 'saved' ? 'SAVED RUN' : 'CURRENT RUN'}</span>
            {meta?.complete_tick_level_reanalysis === false ? (
              <span className="badge">PARTIAL RECONSTRUCTION</span>
            ) : meta?.complete_tick_level_reanalysis ? (
              <span className="badge on">FULL RECONSTRUCTION</span>
            ) : null}
          </div>
          {meta ? (
            <div style={{ marginTop: 8 }}>
              <div className="metric"><span>Runtime status</span><strong>{show(meta.runtime_status)}</strong></div>
              <div className="metric"><span>Run id</span><strong>{show(meta.run_id)}</strong></div>
              <div className="metric"><span>Source</span><strong>{show(meta.source)}</strong></div>
              <div className="metric"><span>Analysis cutoff tick</span><strong>{show(meta.analysis_cutoff_tick)}</strong></div>
              <div className="metric">
                <span>Scientific tick range analyzed</span>
                <strong>{meta.scientific_tick_range[0]}–{meta.scientific_tick_range[1]}</strong>
              </div>
              <div className="metric"><span>Coverage</span><strong>{show(meta.coverage)}</strong></div>
              <div className="metric">
                <span>Complete tick-level re-analysis</span>
                <strong>{meta.complete_tick_level_reanalysis ? 'YES' : 'NO'}</strong>
              </div>
              <div className="subtle">Evidence files: {(meta.evidence_files || []).join(', ') || '—'}</div>
              {meta.used_cumulative_runtime_summaries ? (
                <div className="availability" style={{ marginTop: 6 }}>
                  Cumulative runtime action_counts are available as a separate summary — not reconstructed tick-level history.
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="metric"><span>Analyzed ticks</span><strong>{life?.analyzed_start ?? '—'}–{life?.analyzed_end ?? '—'}</strong></div>
          {life?.phase === 'PAUSED' || life?.phase === 'LIVE' ? (
            <div className="metric"><span>Live runtime tick</span><strong>{life?.live_runtime_tick ?? '—'}</strong></div>
          ) : null}
          <div className="metric"><span>Agents</span><strong>{life?.agents ?? id?.agent_count}</strong></div>
          <div className="metric"><span>Events observed</span><strong>{life?.events_observed ?? 0}</strong></div>
          <div className="metric"><span>Frames sampled</span><strong>{life?.frames_sampled ?? 0}</strong></div>
          <div className="availability">{life?.coverage_reason || analysis.coverage.reason}</div>
          {life?.insufficient ? <div className="na" style={{ marginTop: 8 }}>INSUFFICIENT DATA — extrema and regime claims suppressed until a sensible observation window exists.</div> : null}

          <div className="section-label" style={{ marginTop: 12 }}>EXPORT</div>
          <div className="toolbar-row" style={{ marginTop: 8 }} data-testid="analyzer-export-controls">
            <button
              className="active"
              type="button"
              data-testid="analyzer-copy-report"
              disabled={!exportReady || !onCopyReport}
              onClick={() => onCopyReport?.()}
            >
              COPY REPORT
            </button>
            <button
              type="button"
              data-testid="analyzer-save-markdown"
              disabled={!exportReady || !onSaveMarkdown}
              onClick={() => onSaveMarkdown?.()}
            >
              SAVE .MD
            </button>
            <button
              type="button"
              data-testid="analyzer-save-json"
              disabled={!exportReady || !onSaveJson}
              onClick={() => onSaveJson?.()}
            >
              SAVE .JSON
            </button>
            <button type="button" onClick={onCopy} disabled={!exportReady}>COPY ANALYSIS LOG</button>
            <button type="button" onClick={onDownload} disabled={!exportReady}>DOWNLOAD ANALYSIS LOG</button>
          </div>
        </>
      ) : null}
    </section>

    {!analysis ? null : <>
    <section className="panel science-card wide">
      <h3>RUN SUMMARY</h3>
      <div className="metric"><span>Runtime</span><strong>{id?.runtime}</strong></div>
      <div className="metric"><span>Seed</span><strong>{show(id?.seed)}</strong></div>
      <div className="metric"><span>Generation</span><strong>{show(id?.generation)}</strong></div>
      <div className="metric"><span>Map</span><strong>{show(id?.map_width)}×{show(id?.map_height)} {id?.boundary}</strong></div>
      <div className="metric"><span>Ticks</span><strong>{id?.start_tick}–{id?.end_tick}</strong></div>
      <div className="metric"><span>Duration</span><strong>{id?.duration_ticks}</strong></div>
      <div className="metric"><span>Status</span><strong>{id?.status}</strong></div>
      <div className="subtle">Agents: {id?.agents.map(a => `${a.agent_id}/${a.body_id}/seed=${show(a.seed)}`).join(' · ') || '—'}</div>
      <div className="subtle">Mechanisms: {id?.active_mechanisms.join(', ') || 'NONE / NOT AVAILABLE'}</div>
    </section>

    {meta?.cumulative_runtime_summaries?.length ? (
      <section className="panel science-card wide">
        <h3>CUMULATIVE RUNTIME SUMMARY</h3>
        <div className="availability">
          These counters come from runtime cumulative state. They are NOT tick-level reconstructions
          and must not be used to infer transition timing, streak structure, or phase boundaries.
        </div>
        {meta.cumulative_runtime_summaries.map((row: any, i: number) => (
          <div key={i} className="subtle" style={{ marginTop: 6 }}>
            <b>{row.agent_id}</b> action_counts={JSON.stringify(row.action_counts || {})}
            {row.wait_count != null ? ` · wait=${row.wait_count}` : ''}
            {row.move_count != null ? ` · move=${row.move_count}` : ''}
          </div>
        ))}
      </section>
    ) : null}

    {life?.insufficient ? (
      <section className="panel science-card wide"><div className="na">INSUFFICIENT DATA for per-agent metrics — keep the simulation running.</div></section>
    ) : analysis.agents.map(a => (
      <section className="panel science-card" key={a.agent_id}>
        <h3>{a.agent_id.toUpperCase()}</h3>
        <div className="subtle">seed {show(a.seed)} · {a.body_id} · canonical action ticks {a.ticks_observed}</div>
        {(analysis as any).composite_motor?.authoritative ? (() => {
          const cm = (analysis as any).composite_motor;
          const ag = cm.agents?.[a.agent_id];
          return (
            <>
              <h4>COMPOSITE MOTOR FORENSICS</h4>
              <div className="subtle">Authoritative schema {cm.schema}. Control ≠ effector-active ticks.</div>
              {ag ? (
                <>
                  <div className="metric"><span>Locomotion ticks</span><strong>{ag.locomotion_ticks}</strong></div>
                  <div className="metric"><span>Neck-control ticks</span><strong>{ag.neck_control_ticks}</strong></div>
                  <div className="metric"><span>Oscillator-control ticks</span><strong>{ag.oscillator_control_ticks}</strong></div>
                  <div className="metric"><span>OSC_EMIT selections</span><strong>{ag.control_vs_effector?.OSC_EMIT_selections}</strong></div>
                  <div className="metric"><span>Emission active ticks</span><strong>{ag.control_vs_effector?.emission_active_ticks}</strong></div>
                  <div className="metric"><span>Push ticks</span><strong>{ag.push_ticks}</strong></div>
                  <div className="subtle">combinations {show(ag.combinations)}</div>
                </>
              ) : null}
              <h4>LEGACY PROJECTION (canonical one-label occupancy)</h4>
            </>
          );
        })() : null}
        <h4>TICK-LEVEL ACTION OCCUPANCY{(analysis as any).composite_motor?.authoritative ? ' — LEGACY PROJECTION' : ''}</h4>
        <div className="subtle">One canonical action per (simulation tick, agent). Not selection-event counts.</div>
        <div className="metric"><span>WAIT ticks</span><strong>{show(a.actions.wait_count)} ({show(a.actions.wait_pct)}%)</strong></div>
        <div className="metric"><span>MOVE ticks</span><strong>{show(a.actions.move_count)} ({show(a.actions.move_pct)}%)</strong></div>
        <div className="metric"><span>Occupancy total</span><strong>{a.actions.occupancy_total} ≤ {a.ticks_observed}</strong></div>
        <div className="subtle">dist {show(a.actions.move_distribution)}</div>
        <div className="subtle">longest WAIT streak {show(a.actions.longest_wait_streak)} · MOVE {show(a.actions.longest_move_streak)}</div>
        <div className="subtle">transitions {show(a.actions.action_transitions)}</div>
        {a.cumulative_runtime_action_counts !== 'NOT AVAILABLE' ? (
          <>
            <h4>CUMULATIVE RUNTIME ACTION COUNTS</h4>
            <div className="availability">
              Cognition metrics.action_counts for the full runtime so far. Separate from tick-level occupancy; not merged into WAIT/MOVE ticks above.
            </div>
            <div className="subtle">{show(a.cumulative_runtime_action_counts)}</div>
          </>
        ) : null}
        <h4>ACTION / SCENARIO SELECTION EVENTS</h4>
        <div className="metric"><span>SCENARIO_SELECTED</span><strong>{show(a.cognition.scenario_selected)}</strong></div>
        <div className="subtle">scenario WAIT/MOVE {show(a.cognition.scenario_selected_wait)}/{show(a.cognition.scenario_selected_move)}</div>
        <div className="metric"><span>Cognitive WAIT</span><strong>{show(a.cognition.cognitive_wait_selections)}</strong></div>
        <div className="metric"><span>Fallback WAIT</span><strong>{show(a.cognition.fallback_wait_selections)}</strong></div>
        <div className="subtle">sources {show(a.cognition.selected_action_sources)}</div>
        <h4>TRAJECTORY</h4>
        {(a.movement as any).path_vs_velocity_consistency === 'FLAG' ? (
          <div className="availability" style={{ color: '#b45309' }}>
            WARNING: trajectory metrics inconsistent with runtime displacement (ratio {show((a.movement as any).path_vs_velocity_ratio)})
          </div>
        ) : null}
        <div className="metric"><span>Path (euclid)</span><strong>{show((a.movement as any).path_length_euclidean)}</strong></div>
        <div className="metric"><span>Net</span><strong>{show(a.movement.net_displacement)}</strong></div>
        <div className="metric"><span>Max excursion</span><strong>{show((a.movement as any).max_excursion_from_start)}</strong></div>
        <div className="metric"><span>Unwrapped Δ</span><strong>({show((a.movement as any).unwrapped_dx)}, {show((a.movement as any).unwrapped_dy)})</strong></div>
        <div className="metric"><span>Cell crossings</span><strong>{show((a.movement as any).cell_boundary_crossings)}</strong></div>
        <div className="metric"><span>Boundary wraps</span><strong>x {show((a.movement as any).boundary_crossings_x)} · y {show((a.movement as any).boundary_crossings_y)}</strong></div>
        <div className="subtle">Requested: WAIT {show(a.actions.wait_pct)}% · MOVE {show(a.actions.move_pct)}%</div>
        <div className="subtle">Physical during WAIT {show((a.movement as any).path_during_requested_WAIT)} · during MOVE {show((a.movement as any).path_during_requested_MOVE)}</div>
        <div className="subtle">Local context: cell {show((a.movement as any).current_cell)} · neighborhood replacements {show((a.movement as any).neighborhood_replacements)}</div>
        <div className="subtle">unique_pos_ticks {show((a.movement as any).unique_position_ticks)} · dup_ignored {show((a.movement as any).duplicate_observer_samples_ignored)} · gaps {show((a.movement as any).trajectory_gaps_skipped)}</div>
        <div className="metric"><span>Distance (manhattan)</span><strong>{show(a.movement.distance_travelled)}</strong></div>
        <div className="metric"><span>Max speed</span><strong>{show(a.movement.max_speed)}</strong></div>
        <div className="metric"><span>Unique cells</span><strong>{show(a.movement.unique_cells)}</strong></div>
        <h4>RESOURCES (DEVELOPMENT_FIXTURE — not canonical ontology)</h4>
        <div className="availability">
          resource-* entities exercise contact, transfer, work, and ecology mechanisms. They are not food, rewards, goals, or canonical world objects.
        </div>
        <div className="subtle">A {show(a.resources.resource_A)}</div>
        <div className="subtle">B {show(a.resources.resource_B)}</div>
        <div className="subtle">work {show(a.resources.work_reservoir)}</div>
        <h4>COGNITION</h4>
        <div className="metric"><span>Predictions</span><strong>{show(a.cognition.prediction_count)}</strong></div>
        <div className="metric"><span>Prospective</span><strong>{show(a.cognition.prospective_compositions)}</strong></div>
        <h4>SIGNALS</h4>
        <div className="subtle">emit A/B {a.signals.emissions_A}/{a.signals.emissions_B} · recv A/B {a.signals.receptions_A}/{a.signals.receptions_B}</div>
        <div className="subtle">contact emit {a.signals.contact_triggered_emissions} · motion emit {a.signals.motion_triggered_emissions}</div>
        <div className="subtle">attr mixed/not_unique/unknown {a.signals.reception_attribution.mixed}/{a.signals.reception_attribution.not_unique}/{a.signals.reception_attribution.unknown}</div>
        <h4>VISION</h4>
        <div className="subtle">Physical visual exposure ≠ recognition · Sensor change ≠ interpretation</div>
        <div className="metric"><span>Exposures</span><strong>{show(a.vision?.foreign_body_exposure_ticks)}</strong></div>
        <div className="metric"><span>Episodes</span><strong>{show(a.vision?.observed_exposure_episodes)}</strong></div>
        <div className="metric"><span>Vision-only</span><strong>{show(a.vision?.vision_only_episodes)}</strong></div>
        <div className="metric"><span>Body optical Δ</span><strong>{show(a.vision?.peak_body_optical_contribution)}</strong></div>
        <div className="metric"><span>Cognition link</span><strong>{a.vision?.cognition_linkage ?? 'NOT_ESTABLISHED'}</strong></div>
        <h4>INTERACTION</h4>
        <div className="subtle">contacts {show(a.interaction.body_body_contacts)} · cross-agent {a.interaction.cross_agent_signal_contributions}</div>
      </section>
    ))}

    {!life?.insufficient && analysis.comparison ? (
      <section className="panel science-card wide">
        <h3>AGENT COMPARISON</h3>
        <div className="dashboard-grid">
          {analysis.comparison.rows.map(r => (
            <div key={r.metric} className="metric"><span>{r.metric}</span><strong>A0 {show(r.agent_0)} · A1 {show(r.agent_1)}</strong></div>
          ))}
        </div>
        <h4>Divergences (factual)</h4>
        {analysis.comparison.divergences.length
          ? analysis.comparison.divergences.map((d, i) => <div key={i} className="subtle">{d}</div>)
          : <div className="na">NONE</div>}
      </section>
    ) : null}

    {!life?.insufficient ? <>
    <section className="panel science-card wide">
      <h3>INTERACTION ANALYSIS</h3>
      <div className="metric"><span>First contact</span><strong>{show(analysis.interactions.first_contact_tick)}</strong></div>
      <div className="metric"><span>Contact ticks</span><strong>{analysis.interactions.contact_ticks}</strong></div>
      <div className="metric"><span>Cross-agent contributions</span><strong>{analysis.interactions.cross_agent_contributions}</strong></div>
      <div className="metric"><span>Contact emissions</span><strong>{analysis.interactions.contact_triggered_emissions}</strong></div>
      <h4>Episodes</h4>
      {analysis.interactions.contact_episodes.length
        ? analysis.interactions.contact_episodes.map((ep, i) =>
          <div key={i} className="subtle">t{ep.start}–t{ep.end} ({ep.ticks} ticks)</div>)
        : <div className="na">NONE</div>}
      <h4>Causal snippets</h4>
      {analysis.interactions.causal_snippets.map((sn, i) => (
        <div key={i} className="science-card" style={{ padding: 8, marginBottom: 6 }}>
          <b>tick {sn.tick}</b> <span className="badge">{sn.evidence_class}</span>
          {sn.steps.map((s, j) => <div key={j} className="subtle">→ {s}</div>)}
        </div>
      ))}
      {analysis.interactions.notes.map((n, i) => <div key={i} className="availability">{n}</div>)}
    </section>

    <section className="panel science-card wide">
      <h3>IMPORTANT EVENTS</h3>
      {analysis.important_events.length ? analysis.important_events.map((ev, i) => (
        <button key={i} className="edge-row" style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 4 }}
          onClick={() => onInspectTick(ev.tick)}>
          <b>t{ev.tick}</b> [{ev.category}] {ev.title}
          <div className="subtle">Reason: {ev.reason}</div>
          <div className="subtle">{ev.evidence_class}</div>
        </button>
      )) : <div className="na">NONE</div>}
    </section>

    <section className="panel science-card wide">
      <h3>CAUSAL CHAINS</h3>
      {analysis.causal_chains.length ? analysis.causal_chains.map(ch => (
        <div key={ch.id} className="science-card" style={{ padding: 8, marginBottom: 6 }}>
          <b>{ch.id}</b> @ t{ch.tick}
          <div className="subtle">{ch.nodes.join(' → ')}</div>
          {ch.edges.map((e, i) => (
            <div key={i} className="subtle">{e.from} =[{e.link}]⇒ {e.to}</div>
          ))}
        </div>
      )) : <div className="na">NONE / NOT ESTABLISHED</div>}
    </section>

    <section className="panel science-card wide">
      <h3>VISUAL FORENSICS</h3>
      <div className="subtle">Physical visual exposure ≠ recognition. Sensor change ≠ interpretation. Temporal follow-up ≠ causal behavioral effect.</div>
      {analysis.vision_forensics ? (
        <>
          <div className="metric"><span>Coverage</span><strong>{analysis.vision_forensics.coverage}</strong></div>
          <div className="metric"><span>Authority</span><strong>{analysis.vision_forensics.optical_history_authority || '—'}</strong></div>
          <div className="metric"><span>Exposure ticks</span><strong>{String(analysis.vision_forensics.summary.total_exposure_ticks)}</strong></div>
          <div className="metric"><span>Episodes</span><strong>{String(analysis.vision_forensics.summary.exposure_episodes)}</strong></div>
          <div className="metric"><span>Peak body</span><strong>{String(analysis.vision_forensics.summary.peak_body_contribution)}</strong></div>
          <div className="metric"><span>First exposure</span><strong>{
            analysis.vision_forensics.summary.first_observed_exposure_status === 'NOT_AVAILABLE'
              ? 'NOT_AVAILABLE'
              : analysis.vision_forensics.summary.first_observed_body_optical_exposure
                ? `t${analysis.vision_forensics.summary.first_observed_body_optical_exposure.tick}`
                : 'NONE'
          }</strong></div>
          <div className="metric"><span>Cognition link</span><strong>{analysis.vision_forensics.summary.cognition_linkage_default}</strong></div>
        </>
      ) : (
        <div className="na">NOT_AVAILABLE — no optical series</div>
      )}
    </section>

    <section className="panel science-card wide">
      <h3>PHASES</h3>
      {analysis.phases.map((ph, i) => (
        <div key={i} className="subtle"><b>{ph.start}–{ph.end}</b> {ph.name} — {ph.reason}</div>
      ))}
    </section>
    </> : null}

    <section className="panel science-card wide">
      <h3>DATA COVERAGE</h3>
      <div className="subtle">level: {analysis.coverage.level}</div>
      <div className="subtle">reason: {analysis.coverage.reason}</div>
      <div className="subtle">world: {analysis.coverage.world}</div>
      <div className="subtle">body: {analysis.coverage.body}</div>
      <div className="subtle">cognition: {analysis.coverage.cognition}</div>
      <div className="subtle">signals: {analysis.coverage.signals}</div>
      <div className="subtle">causal provenance: {analysis.coverage.causal_provenance}</div>
      <div className="subtle">
        samples timeline/events/telemetry: {analysis.coverage.timeline_samples}/{analysis.coverage.event_samples}/{analysis.coverage.telemetry_samples}
        {' · '}
        unique simulation ticks: {analysis.coverage.unique_simulation_ticks ?? '—'}
      </div>
    </section>

    {(() => {
      const c1 = (analysis as any).canonical_physical_field_sonification
        || (analysis as any).evidence_extras?.canonical_physical_field_sonification;
      if (!c1) {
        return (
          <section className="panel science-card wide" data-testid="analyze-c1-legacy">
            <h3>CANONICAL PHYSICAL-FIELD SONIFICATION</h3>
            <div className="subtle">CANONICAL_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE (or not attached to this analysis package)</div>
            <div className="subtle">Playback state did not affect simulation. ORIGINAL / HUMAN-AUDIBLE = NOT AVAILABLE.</div>
          </section>
        );
      }
      const prog = c1.progress || {};
      const pct = prog.percent;
      return (
        <section className="panel science-card wide" data-testid="analyze-c1-section">
          <h3>CANONICAL PHYSICAL-FIELD SONIFICATION</h3>
          <div className="subtle" data-testid="analyze-c1-warning">
            {c1.warning_label || 'TRANSFORMED PLAYBACK OF ABSTRACT PHYSICAL FIELD · NOT PHYSICAL Hz · NOT SPL · NOT ORIGINAL HUMAN-AUDIBLE'}
          </div>
          <div className="subtle">profile={c1.profile} · authority={c1.authority_class} · playback_affected_simulation={String(c1.playback_affected_simulation)}</div>
          <div className="subtle">carriers (playback only, NOT physical Hz): {JSON.stringify(c1.canonical_playback_carrier_hz)}</div>
          {pct != null && prog.total > 0 ? (
            <div data-testid="analyze-c1-progress" style={{ marginTop: 8 }}>
              <div className="subtle">C1 schedule progress: {prog.completed}/{prog.total} ({Number(pct).toFixed(1)}%)</div>
              <div role="progressbar" aria-valuenow={Number(pct)} aria-valuemin={0} aria-valuemax={100}
                style={{ height: 10, background: '#333', borderRadius: 2 }}>
                <div style={{ width: `${Math.max(0, Math.min(100, Number(pct)))}%`, height: '100%', background: '#8af', borderRadius: 2 }} />
              </div>
            </div>
          ) : (
            <div className="subtle" data-testid="analyze-c1-live-indefinite">No fabricated percent for indefinite/unavailable monitor</div>
          )}
        </section>
      );
    })()}

    {(() => {
      const sav = (analysis as any).selected_organism_auditory_view
        || (analysis as any).evidence_extras?.selected_organism_auditory_view;
      if (!sav) {
        return (
          <section className="panel science-card wide" data-testid="analyze-sav1-legacy">
            <h3>SELECTED ORGANISM AUDITORY VIEW</h3>
            <div className="subtle">SELECTED_ORGANISM_AUDITORY_VIEW_UNAVAILABLE_LEGACY_EVIDENCE</div>
            <div className="subtle">No mind reading · playback not inferred · not reconstructed from stream/probe/cognition</div>
          </section>
        );
      }
      const prog = sav.progress || {};
      const pct = prog.percent;
      return (
        <section className="panel science-card wide" data-testid="analyze-sav1-section">
          <h3>SELECTED ORGANISM AUDITORY VIEW</h3>
          <div className="subtle" data-testid="analyze-sav1-warning">
            {sav.warning_label || 'ORGANISM SENSORY CHANNEL MONITOR · POST-PHENOTYPE · PRE-COGNITION · NOT HUMAN HEARING · NOT MIND READING'}
          </div>
          <div className="subtle">
            status={sav.status} · boundary={sav.boundary} · agents={JSON.stringify(sav.agent_ids || [])}
            {' · '}receipts={sav.receipt_count ?? 0} · ticks={JSON.stringify(sav.tick_range || null)}
            {' · '}mind_reading={String(sav.mind_reading)} · playback_affected_simulation={String(sav.playback_affected_simulation)}
          </div>
          {pct != null && prog.total > 0 ? (
            <div data-testid="analyze-sav1-progress" style={{ marginTop: 8 }}>
              <div className="subtle">A5 receipt progress: {prog.completed}/{prog.total} ({Number(pct).toFixed(1)}%)</div>
              <div role="progressbar" aria-valuenow={Number(pct)} aria-valuemin={0} aria-valuemax={100}
                style={{ height: 10, background: '#333', borderRadius: 2 }}>
                <div style={{ width: `${Math.max(0, Math.min(100, Number(pct)))}%`, height: '100%', background: '#8af', borderRadius: 2 }} />
              </div>
            </div>
          ) : (
            <div className="subtle" data-testid="analyze-sav1-live-indefinite">No fabricated percent for indefinite/unavailable monitor</div>
          )}
        </section>
      );
    })()}

    {(() => {
      const sovv = (analysis as any).selected_organism_volumetric_vision_view
        || (analysis as any).evidence_extras?.selected_organism_volumetric_vision_view
        || (analysis as any).selected_organism_volumetric_vision_causal;
      if (!sovv) {
        return (
          <section className="panel science-card wide" data-testid="analyze-sovv-legacy">
            <h3>SELECTED ORGANISM VOLUMETRIC VISION</h3>
            <div className="subtle">SELECTED_ORGANISM_VOLUMETRIC_VISION_UNAVAILABLE_LEGACY_EVIDENCE</div>
            <div className="subtle">
              Legacy policy: receptor-only fallback when exact VW6 trace absent · volumetric geometry unavailable · no pixel inference
            </div>
          </section>
        );
      }
      const stages = sovv.stages || sovv.causal?.stages || [];
      const processed = sovv.processed ?? sovv.causal?.processed ?? stages.length;
      const total = sovv.total ?? sovv.causal?.total ?? stages.length;
      return (
        <section className="panel science-card wide" data-testid="analyze-sovv-section">
          <h3>SELECTED ORGANISM VOLUMETRIC VISION</h3>
          <div className="subtle" data-testid="analyze-sovv-banner">
            NOT A CAMERA · NOT RENDERER PIXELS · NOT MIND READING
          </div>
          <div className="subtle" data-testid="analyze-sovv-policy">
            policy={sovv.policy || sovv.causal?.policy || '—'} · available={String(sovv.available ?? true)}
          </div>
          <div className="subtle" data-testid="analyze-sovv-causal">
            Causal: eye pose → sample → XYZ → FOV/range → VW1 LOS → receptor → phenotype → cognition boundary
          </div>
          {total > 0 ? (
            <div data-testid="analyze-sovv-progress" className="subtle">
              Stages processed {processed}/{total} (finite exact counts — no fabricated bar)
            </div>
          ) : (
            <div className="subtle" data-testid="analyze-sovv-no-progress">No fabricated percent</div>
          )}
          {stages.length ? (
            <ol data-testid="analyze-sovv-stages">
              {stages.map((s: string) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          ) : null}
        </section>
      );
    })()}

    {(() => {
      const sav2 = (analysis as any).selected_organism_auditory_sonification
        || (analysis as any).evidence_extras?.selected_organism_auditory_sonification;
      if (!sav2) {
        return (
          <section className="panel science-card wide" data-testid="analyze-sav2-legacy">
            <h3>SELECTED ORGANISM AUDITORY SONIFICATION</h3>
            <div className="subtle">SELECTED_ORGANISM_AUDITORY_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE</div>
            <div className="subtle">No mind reading · not reconstructed from stream/probe/cognition · not literal organism sound</div>
          </section>
        );
      }
      const prog = sav2.progress || {};
      const pct = prog.percent;
      return (
        <section className="panel science-card wide" data-testid="analyze-sav2-section">
          <h3>SELECTED ORGANISM AUDITORY SONIFICATION</h3>
          <div className="subtle" data-testid="analyze-sav2-warning">
            {sav2.warning_label || 'TRANSLATED MONITOR OF ORGANISM RECEPTOR CHANNELS · POST-PHENOTYPE · PRE-COGNITION · NOT HUMAN HEARING · NOT MIND READING'}
          </div>
          <div className="subtle">
            status={sav2.status} · profile={sav2.profile} · authority={sav2.authority_class}
            {' · '}mapping={sav2.amplitude_mapping} · routing={sav2.channel_mode}
            {' · '}agents={JSON.stringify(sav2.agent_ids || [])}
            {' · '}receipts={sav2.sav1_receipt_count ?? 0}
            {' · '}mind_reading={String(sav2.mind_reading)}
            {' · '}playback_affected_simulation={String(sav2.playback_affected_simulation)}
          </div>
          <div className="subtle">{sav2.carrier_label || 'PLAYBACK CARRIERS — NOT PHYSICAL OR ORGANISM FREQUENCIES'}</div>
          {pct != null && prog.total > 0 ? (
            <div data-testid="analyze-sav2-progress" style={{ marginTop: 8 }}>
              <div className="subtle">SAV2 provenance progress: {prog.completed}/{prog.total} ({Number(pct).toFixed(1)}%)</div>
              <div role="progressbar" aria-valuenow={Number(pct)} aria-valuemin={0} aria-valuemax={100}
                style={{ height: 10, background: '#333', borderRadius: 2 }}>
                <div style={{ width: `${Math.max(0, Math.min(100, Number(pct)))}%`, height: '100%', background: '#8af', borderRadius: 2 }} />
              </div>
            </div>
          ) : (
            <div className="subtle" data-testid="analyze-sav2-live-indefinite">No fabricated percent for indefinite/unavailable monitor</div>
          )}
        </section>
      );
    })()}

    {(() => {
      const sav4a = (analysis as any).selected_organism_auditory_offline_reconstruction
        || (analysis as any).evidence_extras?.selected_organism_auditory_offline_reconstruction;
      if (!sav4a) {
        return (
          <section className="panel science-card wide" data-testid="analyze-sav4a-legacy">
            <h3>OFFLINE AUDITORY RECONSTRUCTION · SAV4A</h3>
            <div className="subtle">SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_UNAVAILABLE_LEGACY_EVIDENCE</div>
            <div className="subtle">No audio · gaps≠silence · not reconstructed from stream/probe/cognition/pixels</div>
          </section>
        );
      }
      const phases = sav4a.analyzer_progress?.phases || [];
      return (
        <section className="panel science-card wide" data-testid="analyze-sav4a-section">
          <h3>OFFLINE AUDITORY RECONSTRUCTION · SAV4A</h3>
          <div className="subtle" data-testid="analyze-sav4a-warning">
            {sav4a.warning || 'READ-ONLY OVER SAVED EVIDENCE · GAPS ARE NOT SILENCE · NO AUDIO IN SAV4A'}
          </div>
          <div className="subtle">
            available={String(sav4a.available)} · records={sav4a.normalized_record_count ?? 0}
            {' · '}schedule={String(sav4a.schedule_available)} · items={sav4a.schedule_item_count ?? 0}
            {' · '}gaps={sav4a.gap_count ?? 0} · dups={sav4a.duplicate_count ?? 0} · conflicts={sav4a.conflict_count ?? 0}
          </div>
          <div className="subtle">
            authority_matrix={JSON.stringify(sav4a.authority_matrix || {})}
            {' · '}norm_digest={String(sav4a.normalized_record_digest || '').slice(0, 16)}…
            {' · '}sched_digest={String(sav4a.schedule_digest || '').slice(0, 16)}…
          </div>
          <div className="subtle" data-testid="analyze-sav4a-causal">
            {(sav4a.causal_chain || []).join(' → ') || 'saved evidence → schedule'}
          </div>
          <div data-testid="analyze-sav4a-progress" style={{ marginTop: 8 }}>
            {(phases as any[]).map((p: any) => {
              const tot = p.total;
              const indeterminate = tot == null;
              const pct = p.percent;
              return (
                <div key={String(p.phase)} style={{ marginBottom: 6 }} data-testid={`analyze-sav4a-phase-${p.phase}`}>
                  <div className="subtle">
                    {p.phase}: {indeterminate
                      ? `processed=${p.processed} (indeterminate — no invented %)`
                      : `${p.processed}/${tot}${pct != null ? ` (${Number(pct).toFixed(1)}%)` : ''}`}
                  </div>
                  {!indeterminate && tot > 0 && pct != null ? (
                    <div role="progressbar" aria-valuenow={Number(pct)} aria-valuemin={0} aria-valuemax={100}
                      style={{ height: 8, background: '#333', borderRadius: 2 }}>
                      <div style={{ width: `${Math.max(0, Math.min(100, Number(pct)))}%`, height: '100%', background: '#8af', borderRadius: 2 }} />
                    </div>
                  ) : (
                    <div className="subtle" data-testid="analyze-sav4a-indeterminate">phase total unknown while streaming</div>
                  )}
                </div>
              );
            })}
            {!phases.length ? (
              <div className="subtle">No phase progress attached</div>
            ) : null}
          </div>
        </section>
      );
    })()}
    </>}

    {(() => {
      const vpc = (analysis as any)?.volumetric_physical_causal_reconstruction;
      const text = (analysis as any)?.volumetric_physical_causal_report_text;
      if (!vpc && !(typeof text === 'string' && text.trim())) return null;
      const rz = vpc?.relative_z || {};
      const ladder = (vpc?.physical_stories && vpc.physical_stories[0]?.causal_ladder) || null;
      const causeCounts = vpc?.negative_cause_counts || {};
      return (
        <section className="panel science-card wide" data-testid="analyze-volumetric-physical-causal">
          <h3>VOLUMETRIC PHYSICAL CAUSAL STORY</h3>
          <div className="subtle" data-testid="analyze-vpc-banner">
            RESEARCHER RECONSTRUCTION OVER AUTHORITATIVE PHYSICAL RECEIPTS · PRESERVES SCIENTIFIC_V3
          </div>
          <div className="subtle" data-testid="analyze-vpc-model">
            world={show(vpc?.model_authority?.world_dimensionality)} ·
            described_as_2d={show(vpc?.acanthostega_described_as_2d)} ·
            status={show(vpc?.status)}
          </div>
          <div className="subtle" data-testid="analyze-vpc-relative-z">
            relative_z physical_dof={show(rz.physical_dof)} ·
            control_availability={show(rz.control_availability)} ·
            authority={show(rz.control_availability_authority)} ·
            agent_selectable={show(rz.agent_selectable)} ·
            outcome={show(rz.outcome_class)} ·
            morphological_reach={show(rz.morphological_ground_reachability)} ·
            z_requests={show(rz.z_request_nonzero_count)} ·
            ebae_refs={show(rz.ebae_event_refs_indexed)}
          </div>
          <div className="subtle" data-testid="analyze-vpc-negative">
            negative_cause_counts: {show(causeCounts)}
          </div>
          {ladder ? (
            <ol data-testid="analyze-vpc-ladder">
              {Object.entries(ladder).map(([rung, info]: [string, any]) => (
                <li key={rung}>{rung}: {show(info?.status)}{info?.observed_cause ? ` (${info.observed_cause})` : ''}</li>
              ))}
            </ol>
          ) : (
            <div className="subtle">No causal ladder sample (legacy/unavailable)</div>
          )}
          {typeof text === 'string' && text.trim() ? (
            <pre className="log-block" data-testid="analyze-vpc-report" style={{ whiteSpace: 'pre-wrap' }}>{text}</pre>
          ) : null}
        </section>
      );
    })()}

    <section className="panel science-card wide">
      <SignalContextPanel />
    </section>
  </div>;
}
