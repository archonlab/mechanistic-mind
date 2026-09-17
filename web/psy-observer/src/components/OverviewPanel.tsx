import type { KeyFrameRef, ObserverRunRecord, OverviewCard, RunAnalysis } from '../analysis/types';

const OVERVIEW_FILTERS = ['ALL', 'PHYSICAL', 'ACTION', 'BODY', 'RESOURCE', 'COGNITION', 'SIGNAL', 'INTERACTION', 'FIRSTS', 'ANOMALIES'] as const;
const AGENT_FILTERS = ['ALL AGENTS', 'AGENT_0', 'AGENT_1', 'INTERACTIONS'] as const;

export function KeyFrameThumb({ kf, onClick, size = 72 }: { kf: KeyFrameRef; onClick?: () => void; size?: number }) {
  const w = size;
  const h = size;
  const ww = Math.max(1, kf.world_w || 32);
  const hh = Math.max(1, kf.world_h || 32);
  const inner = (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <rect x={0} y={0} width={w} height={h} fill="#0f172a" />
      {kf.agents.map((a, i) => {
        const cx = (((a.x % ww) + ww) % ww) / ww * w;
        const cy = (((a.y % hh) + hh) % hh) / hh * h;
        return <circle key={i} cx={cx} cy={cy} r={4} fill={i === 0 ? '#86efac' : '#fde68a'} />;
      })}
      {kf.contact ? <text x={4} y={12} fill="#f87171" fontSize={8}>CONTACT</text> : null}
      <text x={4} y={h - 4} fill="#94a3b8" fontSize={8}>t{kf.tick}</text>
    </svg>
  );
  if (!onClick) {
    return <div style={{ width: w, height: h, border: '1px solid #334155', background: '#0f172a' }}>{inner}</div>;
  }
  return (
    <button onClick={onClick} title={`Key frame t${kf.tick}: ${kf.reason}`}
      style={{ width: w, height: h, padding: 0, border: '1px solid #334155', background: '#0f172a', flexShrink: 0 }}>
      {inner}
    </button>
  );
}

/** OVERVIEW = bounded run catalog. */
export function OverviewCatalogPanel({
  runs,
  currentRunId,
  onOpenRun,
  onAnalysisLog,
  onReplay,
}: {
  runs: ObserverRunRecord[];
  currentRunId: string | null;
  onOpenRun: (runId: string) => void;
  onAnalysisLog: (run: ObserverRunRecord) => void;
  onReplay?: (run: ObserverRunRecord) => void;
}) {
  return <div className="dashboard-grid">
    <section className="panel science-card wide">
      <h3>OVERVIEW · RUN CATALOG</h3>
      <div className="subtle">
        Bounded history of Observer runs. OPEN RUN shows the human-readable interpretation.
        Analyze Results remains the technical analysis of the current run.
      </div>
      <div className="toolbar-row" style={{ marginTop: 8 }}>
        <button disabled title="NOT YET IMPLEMENTED">COMPARE RUNS — NOT YET IMPLEMENTED</button>
      </div>
    </section>

    {!runs.length ? (
      <section className="panel science-card wide"><div className="na">No archived runs yet. Start/pause/stop a simulation — analysis archives automatically.</div></section>
    ) : runs.map((run) => (
      <section className="panel science-card wide" key={run.run_id}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          {run.thumbnail
            ? <KeyFrameThumb kf={run.thumbnail} size={96} onClick={() => onOpenRun(run.run_id)} />
            : <div className="na" style={{ width: 96, height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid #334155' }}>THUMBNAIL NOT AVAILABLE</div>}
          <div style={{ flex: 1 }}>
            <div className="inspecting-banner">
              <strong>RUN #{run.run_number}</strong>
              <span className="badge">{run.status}</span>
              {run.run_id === currentRunId ? <span className="badge on">CURRENT</span> : null}
              {run.experimental ? <span className="badge">EXPERIMENTAL</span> : <span className="badge">CANONICAL/DEFAULT</span>}
            </div>
            <div className="subtle">id {run.run_id}</div>
            <div className="metric"><span>Seed</span><strong>{run.base_seed ?? '—'}</strong></div>
            <div className="metric"><span>Runtime</span><strong>{run.runtime_type}</strong></div>
            <div className="metric"><span>Generation</span><strong>{run.runtime_generation ?? '—'}</strong></div>
            <div className="metric"><span>Map</span><strong>{run.map.width}×{run.map.height} {run.map.boundary}</strong></div>
            <div className="metric"><span>Agents</span><strong>{run.agents.length}</strong></div>
            <div className="metric"><span>Ticks</span><strong>{run.initial_tick}–{run.final_tick}</strong></div>
            <div className="metric"><span>Started</span><strong>{run.started_at}</strong></div>
            <div className="metric"><span>Finished</span><strong>{run.finished_at || '—'}</strong></div>
            <div className="subtle">fingerprint {run.config_fingerprint}</div>
            <div className="subtle">
              First contact: {run.summary.first_contact_tick ?? 'NOT AVAILABLE'} ·
              Signals: {run.summary.signals_observed} ·
              Cross-agent: {run.summary.cross_agent_contributions} ·
              Important: {run.summary.important_events} ·
              Anomalies: {run.summary.anomalies}
            </div>
            <div className="subtle">
              Agents: {run.agents.map((a) => `${a.agent_id}/${a.body_id}/seed=${a.seed ?? '—'}`).join(' · ')}
            </div>
            <div className="toolbar-row" style={{ marginTop: 8 }}>
              <button className="active" onClick={() => onOpenRun(run.run_id)}>OPEN RUN</button>
              <button onClick={() => onAnalysisLog(run)}>ANALYSIS LOG</button>
              {onReplay ? <button onClick={() => onReplay(run)}>REPLAY</button> : null}
            </div>
          </div>
        </div>
      </section>
    ))}
  </div>;
}

/** OPEN RUN = former Overview narrative for one archived/current run. */
export function RunDetailPanel({
  run,
  filter,
  setFilter,
  agentFilter,
  setAgentFilter,
  onBack,
  onInspectTick,
  onViewEvidence,
}: {
  run: ObserverRunRecord;
  filter: string;
  setFilter: (v: string) => void;
  agentFilter: string;
  setAgentFilter: (v: string) => void;
  onBack: () => void;
  onInspectTick: (tick: number) => void;
  onViewEvidence: (card: OverviewCard) => void;
}) {
  const analysis: RunAnalysis = run.analysis;
  const cards = analysis.overview || [];
  const visible = cards.filter((c) => {
    if (filter !== 'ALL') {
      if (filter === 'FIRSTS' && c.kind !== 'KEY') return false;
      if (filter === 'ANOMALIES' && !c.title.includes('ANOMALY') && !c.title.includes('LONG WAIT') && !c.title.includes('LIMITATION')) return false;
      if (filter !== 'FIRSTS' && filter !== 'ANOMALIES' && c.category !== filter && c.kind !== 'PHASE' && c.kind !== 'QUIET') return false;
    }
    if (agentFilter === 'AGENT_0') return !c.agent_filter.length || c.agent_filter.includes('agent_0');
    if (agentFilter === 'AGENT_1') return !c.agent_filter.length || c.agent_filter.includes('agent_1');
    if (agentFilter === 'INTERACTIONS') {
      return c.category === 'INTERACTION' || c.category === 'SIGNAL' || c.title.includes('CONTACT') || c.title.includes('CROSS-AGENT');
    }
    return true;
  });

  return <div className="dashboard-grid">
    <section className="panel science-card wide">
      <div className="toolbar-row">
        <button onClick={onBack}>← BACK TO RUNS</button>
      </div>
      <h3>RUN #{run.run_number}</h3>
      <div className="subtle">
        Seed {run.base_seed ?? '—'} · {run.runtime_type} · ticks {run.initial_tick}–{run.final_tick} · {run.status}
      </div>
      <div className="subtle">run_id {run.run_id} · generation {run.runtime_generation ?? '—'} · fingerprint {run.config_fingerprint}</div>
      <div className="subtle">Coverage: {analysis.lifecycle?.coverage || analysis.coverage.level} — {analysis.lifecycle?.coverage_reason || analysis.coverage.reason}</div>
    </section>

    <section className="panel science-card wide">
      <h3>SUMMARY</h3>
      <div className="subtle">First contact t{run.summary.first_contact_tick ?? '—'} · signals {run.summary.signals_observed} · cross-agent {run.summary.cross_agent_contributions}</div>
      <div className="subtle">Important {run.summary.important_events} · anomalies {run.summary.anomalies} · contact ticks {run.summary.contact_ticks}</div>
      {run.thumbnail ? <KeyFrameThumb kf={run.thumbnail} size={120} onClick={() => onInspectTick(run.thumbnail!.tick)} /> : <div className="na">THUMBNAIL NOT AVAILABLE</div>}
    </section>

    <section className="panel science-card wide">
      <h3>PHASES</h3>
      {analysis.phases.length ? analysis.phases.map((ph, i) => (
        <div key={i} className="subtle"><b>{ph.start}–{ph.end}</b> {ph.name} — {ph.reason}</div>
      )) : <div className="na">NOT AVAILABLE</div>}
    </section>

    <section className="panel science-card wide">
      <h3>IMPORTANT EVENTS</h3>
      {analysis.important_events.length ? analysis.important_events.map((ev, i) => (
        <div key={i} className="subtle"><b>t{ev.tick}</b> [{ev.category}] {ev.title} — {ev.reason}</div>
      )) : <div className="na">NONE</div>}
    </section>

    <section className="panel science-card wide">
      <h3>INTERACTIONS</h3>
      {analysis.interactions.causal_snippets.map((sn, i) => (
        <div key={i} className="subtle">t{sn.tick} [{sn.evidence_class}] {sn.steps.join(' → ')}</div>
      ))}
      {!analysis.interactions.causal_snippets.length ? <div className="na">NONE</div> : null}
    </section>

    <section className="panel science-card wide">
      <h3>ANOMALIES</h3>
      {analysis.important_events.filter((e) => e.category === 'ANOMALY').length
        ? analysis.important_events.filter((e) => e.category === 'ANOMALY').map((ev, i) => (
          <div key={i} className="subtle">t{ev.tick} {ev.title}</div>
        ))
        : <div className="na">NONE</div>}
    </section>

    <section className="panel science-card wide">
      <h3>HUMAN-READABLE TIMELINE</h3>
      <div className="toolbar-row">
        {OVERVIEW_FILTERS.map((f) =>
          <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>{f}</button>)}
      </div>
      <div className="toolbar-row">
        {AGENT_FILTERS.map((f) =>
          <button key={f} className={agentFilter === f ? 'active' : ''} onClick={() => setAgentFilter(f)}>{f}</button>)}
      </div>
    </section>

    {visible.length ? visible.map((card) => (
      <section className="panel science-card wide" key={card.id}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          {card.keyframe ? <KeyFrameThumb kf={card.keyframe} onClick={() => onInspectTick(card.keyframe!.tick)} /> : null}
          <div style={{ flex: 1 }}>
            <div className="inspecting-banner">
              <strong>
                {card.tick_start === card.tick_end ? `TICK ${card.tick_start}` : `TICKS ${card.tick_start}–${card.tick_end}`}
              </strong>
              <span className="badge">{card.kind}</span>
              <span className="badge">{card.evidence_class}</span>
            </div>
            <h3 style={{ marginTop: 6 }}>{card.title}</h3>
            <p className="subtle" style={{ whiteSpace: 'pre-wrap' }}>{card.body}</p>
            <div className="toolbar-row">
              <button onClick={() => onViewEvidence(card)}>VIEW EVIDENCE</button>
              <button onClick={() => onInspectTick(card.evidence.frame_tick ?? card.tick_start)}>INSPECT FRAME</button>
            </div>
          </div>
        </div>
      </section>
    )) : <section className="panel science-card wide"><div className="na">No timeline cards for this filter.</div></section>}

    <section className="panel science-card wide">
      <h3>KEY FRAMES</h3>
      <div className="toolbar-row" style={{ flexWrap: 'wrap' }}>
        {(analysis.keyframes || []).map((kf, i) => (
          <KeyFrameThumb key={i} kf={kf} onClick={() => onInspectTick(kf.tick)} />
        ))}
        {!analysis.keyframes?.length ? <div className="na">NOT AVAILABLE</div> : null}
      </div>
    </section>

    <section className="panel science-card wide">
      <h3>CAUSAL EVIDENCE</h3>
      {analysis.causal_chains.length ? analysis.causal_chains.map((ch) => (
        <div key={ch.id} className="subtle">{ch.nodes.join(' → ')} @ t{ch.tick}</div>
      )) : <div className="na">NONE / NOT ESTABLISHED</div>}
    </section>

    <section className="panel science-card wide">
      <h3>DATA COVERAGE</h3>
      <div className="subtle">{analysis.coverage.level}: {analysis.coverage.reason}</div>
    </section>
  </div>;
}

/** Compatibility wrapper used by App: catalog or detail. */
export function OverviewPanel(props: {
  runs: ObserverRunRecord[];
  currentRunId: string | null;
  openRunId: string | null;
  setOpenRunId: (id: string | null) => void;
  filter: string;
  setFilter: (v: string) => void;
  agentFilter: string;
  setAgentFilter: (v: string) => void;
  onInspectTick: (tick: number) => void;
  onViewEvidence: (card: OverviewCard) => void;
  onAnalysisLog: (run: ObserverRunRecord) => void;
}) {
  const open = props.openRunId ? props.runs.find((r) => r.run_id === props.openRunId) : null;
  if (open) {
    return <RunDetailPanel
      run={open}
      filter={props.filter}
      setFilter={props.setFilter}
      agentFilter={props.agentFilter}
      setAgentFilter={props.setAgentFilter}
      onBack={() => props.setOpenRunId(null)}
      onInspectTick={props.onInspectTick}
      onViewEvidence={props.onViewEvidence}
    />;
  }
  return <OverviewCatalogPanel
    runs={props.runs}
    currentRunId={props.currentRunId}
    onOpenRun={props.setOpenRunId}
    onAnalysisLog={props.onAnalysisLog}
  />;
}
