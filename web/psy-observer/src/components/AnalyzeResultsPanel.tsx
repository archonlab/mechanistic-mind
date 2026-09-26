import { useState } from 'react';
import type { RunAnalysis } from '../analysis/types';
import { SignalContextPanel } from './SignalContextPanel';

function show(v: any) {
  if (v == null || v === 'NOT AVAILABLE') return 'NOT AVAILABLE';
  if (typeof v === 'number' && Number.isFinite(v)) return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
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

export function AnalyzeResultsPanel({
  analysis,
  analyzing,
  analysisProgress,
  analysisSource,
  onAnalysisSourceChange,
  savedRuns,
  selectedRunId,
  onSelectRunId,
  onRefreshRuns,
  onAnalyze,
  onCopy,
  onDownload,
  onInspectTick,
}: {
  analysis: RunAnalysis | null;
  analyzing?: boolean;
  analysisProgress?: string;
  analysisSource: AnalysisSourceMode;
  onAnalysisSourceChange: (s: AnalysisSourceMode) => void;
  savedRuns: RunCatalogEntry[];
  selectedRunId: string | null;
  onSelectRunId: (id: string | null) => void;
  onRefreshRuns: () => void;
  onAnalyze: () => void;
  onCopy: () => void;
  onDownload: () => void;
  onInspectTick: (tick: number) => void;
}) {
  const [showPicker, setShowPicker] = useState(false);
  const meta = analysis?.evidence_meta;
  const id = analysis?.identity;
  const life = analysis?.lifecycle;

  return <div className="dashboard-grid">
    <section className="panel science-card wide">
      <h3>ANALYZE RESULTS</h3>
      <div className="subtle" style={{ marginBottom: 8 }}>
        Analysis is read-only. It does not pause, advance, or modify the scientific runtime.
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
          >
            {analyzing ? (analysisProgress || 'Analyzing…') : 'Analyze'}
          </button>
        </div>
      </fieldset>

      {!analysis ? (
        <div className="na" style={{ marginTop: 12 }}>
          ANALYSIS: waiting — choose a source and press Analyze (or open this tab during a live run for automatic buffer view).
        </div>
      ) : (
        <>
          <div className="inspecting-banner" style={{ marginTop: 12 }}>
            <strong>{life?.banner || `ANALYSIS: ${id?.analysis_mode}`}</strong>
            <span className="badge">{life?.coverage || meta?.coverage || '—'}</span>
            {meta?.complete_tick_level_reanalysis === false ? (
              <span className="badge">PARTIAL RECONSTRUCTION</span>
            ) : meta?.complete_tick_level_reanalysis ? (
              <span className="badge on">FULL RECONSTRUCTION</span>
            ) : null}
          </div>
          {meta ? (
            <div style={{ marginTop: 8 }}>
              <div className="metric"><span>Runtime status</span><strong>{show(meta.runtime_status)}</strong></div>
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
          <div className="toolbar-row" style={{ marginTop: 8 }}>
            <button className="active" onClick={onCopy}>COPY ANALYSIS LOG</button>
            <button onClick={onDownload}>DOWNLOAD ANALYSIS LOG</button>
          </div>
        </>
      )}
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
        <h4>RESOURCES</h4>
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
    </>}

    <section className="panel science-card wide">
      <SignalContextPanel />
    </section>
  </div>;
}
