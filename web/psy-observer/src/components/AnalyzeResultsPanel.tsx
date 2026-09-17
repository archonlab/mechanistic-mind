import type { RunAnalysis } from '../analysis/types';

function show(v: any) {
  if (v == null || v === 'NOT AVAILABLE') return 'NOT AVAILABLE';
  if (typeof v === 'number' && Number.isFinite(v)) return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export function AnalyzeResultsPanel({
  analysis,
  onCopy,
  onDownload,
  onInspectTick,
}: {
  analysis: RunAnalysis | null;
  onCopy: () => void;
  onDownload: () => void;
  onInspectTick: (tick: number) => void;
}) {
  if (!analysis) {
    return <section className="panel science-card"><h3>Analyze Results</h3><div className="na">ANALYSIS: INSUFFICIENT DATA — waiting for Observer telemetry…</div></section>;
  }
  const id = analysis.identity;
  const life = analysis.lifecycle;
  return <div className="dashboard-grid">
    <section className="panel science-card wide" style={{ borderColor: '#334155' }}>
      <div className="inspecting-banner">
        <strong>{life?.banner || `ANALYSIS: ${id.analysis_mode}`}</strong>
        <span className="badge on">AUTOMATIC</span>
        <span className="badge">{life?.coverage || '—'}</span>
      </div>
      <div className="subtle" style={{ marginTop: 6 }}>
        Analysis starts automatically with the run — no Start Analysis button.
        Observer-only; does not alter the scientific runtime.
      </div>
      <div className="metric"><span>Analyzed ticks</span><strong>{life?.analyzed_start ?? '—'}–{life?.analyzed_end ?? '—'}</strong></div>
      {life?.phase === 'PAUSED' || life?.phase === 'LIVE' ? (
        <div className="metric"><span>Live runtime tick</span><strong>{life?.live_runtime_tick ?? '—'}</strong></div>
      ) : null}
      <div className="metric"><span>Agents</span><strong>{life?.agents ?? id.agent_count}</strong></div>
      <div className="metric"><span>Events observed</span><strong>{life?.events_observed ?? 0}</strong></div>
      <div className="metric"><span>Frames sampled</span><strong>{life?.frames_sampled ?? 0}</strong></div>
      <div className="metric"><span>Coverage</span><strong>{life?.coverage ?? '—'}</strong></div>
      <div className="availability">{life?.coverage_reason || analysis.coverage.reason}</div>
      {life?.insufficient ? <div className="na" style={{ marginTop: 8 }}>INSUFFICIENT DATA — extrema and regime claims suppressed until a sensible observation window exists.</div> : null}
      <div className="toolbar-row" style={{ marginTop: 8 }}>
        <button className="active" onClick={onCopy}>COPY ANALYSIS LOG</button>
        <button onClick={onDownload}>DOWNLOAD ANALYSIS LOG</button>
      </div>
    </section>

    <section className="panel science-card wide">
      <h3>RUN SUMMARY</h3>
      <div className="metric"><span>Runtime</span><strong>{id.runtime}</strong></div>
      <div className="metric"><span>Seed</span><strong>{show(id.seed)}</strong></div>
      <div className="metric"><span>Generation</span><strong>{show(id.generation)}</strong></div>
      <div className="metric"><span>Map</span><strong>{show(id.map_width)}×{show(id.map_height)} {id.boundary}</strong></div>
      <div className="metric"><span>Ticks</span><strong>{id.start_tick}–{id.end_tick}</strong></div>
      <div className="metric"><span>Duration</span><strong>{id.duration_ticks}</strong></div>
      <div className="metric"><span>Status</span><strong>{id.status}</strong></div>
      <div className="subtle">Agents: {id.agents.map(a => `${a.agent_id}/${a.body_id}/seed=${show(a.seed)}`).join(' · ') || '—'}</div>
      <div className="subtle">Mechanisms: {id.active_mechanisms.join(', ') || 'NONE / NOT AVAILABLE'}</div>
    </section>

    {life?.insufficient ? (
      <section className="panel science-card wide"><div className="na">INSUFFICIENT DATA for per-agent metrics — keep the simulation running.</div></section>
    ) : analysis.agents.map(a => (
      <section className="panel science-card" key={a.agent_id}>
        <h3>{a.agent_id.toUpperCase()}</h3>
        <div className="subtle">seed {show(a.seed)} · {a.body_id} · ticks {a.ticks_observed}</div>
        <h4>ACTIONS</h4>
        <div className="metric"><span>WAIT</span><strong>{show(a.actions.wait_count)} ({show(a.actions.wait_pct)}%)</strong></div>
        <div className="metric"><span>MOVE</span><strong>{show(a.actions.move_count)} ({show(a.actions.move_pct)}%)</strong></div>
        <div className="subtle">dist {show(a.actions.move_distribution)}</div>
        <div className="subtle">longest WAIT {show(a.actions.longest_wait_streak)} · MOVE {show(a.actions.longest_move_streak)}</div>
        <h4>MOVEMENT</h4>
        <div className="metric"><span>Distance</span><strong>{show(a.movement.distance_travelled)}</strong></div>
        <div className="metric"><span>Net disp.</span><strong>{show(a.movement.net_displacement)}</strong></div>
        <div className="metric"><span>Max speed</span><strong>{show(a.movement.max_speed)}</strong></div>
        <div className="metric"><span>Unique cells</span><strong>{show(a.movement.unique_cells)}</strong></div>
        <h4>RESOURCES</h4>
        <div className="subtle">A {show(a.resources.resource_A)}</div>
        <div className="subtle">B {show(a.resources.resource_B)}</div>
        <div className="subtle">work {show(a.resources.work_reservoir)}</div>
        <h4>COGNITION</h4>
        <div className="metric"><span>Predictions</span><strong>{show(a.cognition.prediction_count)}</strong></div>
        <div className="metric"><span>Prospective</span><strong>{show(a.cognition.prospective_compositions)}</strong></div>
        <div className="metric"><span>SCENARIO_SELECTED</span><strong>{show(a.cognition.scenario_selected)}</strong></div>
        <div className="metric"><span>Cognitive WAIT</span><strong>{show(a.cognition.cognitive_wait_selections)}</strong></div>
        <div className="metric"><span>Fallback WAIT</span><strong>{show(a.cognition.fallback_wait_selections)}</strong></div>
        <div className="subtle">scenario WAIT/MOVE {show(a.cognition.scenario_selected_wait)}/{show(a.cognition.scenario_selected_move)}</div>
        <div className="subtle">sources {show(a.cognition.selected_action_sources)}</div>
        <h4>SIGNALS</h4>
        <div className="subtle">emit A/B {a.signals.emissions_A}/{a.signals.emissions_B} · recv A/B {a.signals.receptions_A}/{a.signals.receptions_B}</div>
        <div className="subtle">contact emit {a.signals.contact_triggered_emissions} · motion emit {a.signals.motion_triggered_emissions}</div>
        <div className="subtle">attr mixed/not_unique/unknown {a.signals.reception_attribution.mixed}/{a.signals.reception_attribution.not_unique}/{a.signals.reception_attribution.unknown}</div>
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
      <div className="subtle">samples timeline/events/telemetry: {analysis.coverage.timeline_samples}/{analysis.coverage.event_samples}/{analysis.coverage.telemetry_samples}</div>
    </section>
  </div>;
}
