/**
 * 4.26–4.28 Observer panel: CONTEXT → PROSPECTION → CONTROL
 * Uses compact mind.contextual_stack on LIVE; FULL detail when available.
 * Explanatory labels only — no INTENTION/PLACE/MAP cognition variables.
 */
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';

type Props = {
  frame: any;
  agentId?: string | null;
  detail?: string;
};

const HISTORY_CAP = 24;

type HistEvt = { tick: number; label: string; key: string };

function stackFromFrame(frame: any, agentId?: string | null) {
  const views = frame?.agents_views || {};
  const aid = agentId || frame?.observer?.selected_agent_id || frame?.header?.selected_agent_id;
  const view = (aid && views[aid]) || views[Object.keys(views)[0]] || null;
  const mind = view?.mind || frame?.mind || {};
  return mind?.contextual_stack || frame?.contextual_stack || null;
}

function fullDetailFromFrame(frame: any, agentId?: string | null) {
  // FULL cognition_public_view sections may live under mind when detail=full
  const views = frame?.agents_views || {};
  const aid = agentId || frame?.observer?.selected_agent_id;
  const view = (aid && views[aid]) || null;
  const mind = view?.mind || frame?.mind || {};
  return {
    cpo: mind?.contextual_predictive_organization || null,
    cgp: mind?.context_grounded_prospection || null,
    ppc: mind?.persistent_prospective_control || null,
  };
}

function stageStyle(active: boolean): CSSProperties {
  return {
    minWidth: 88,
    padding: '6px 8px',
    borderRadius: 6,
    border: `1px solid ${active ? 'var(--accent, #6af)' : 'var(--line, #333)'}`,
    background: active ? 'rgba(80,140,255,0.12)' : 'transparent',
    fontSize: 11,
  };
}

export function ContextualProspectiveControlPanel({ frame, agentId, detail }: Props) {
  const stack = stackFromFrame(frame, agentId);
  const full = fullDetailFromFrame(frame, agentId);
  const tick = Number(frame?.header?.tick ?? frame?.observer?.inspected_tick ?? 0);
  const isFull = String(detail || frame?.observer?.frame_detail || '').toLowerCase() === 'full';

  const ctx = stack?.context || {};
  const prosp = stack?.prospection || {};
  const persist = stack?.persistent_control || {};
  const flags = stack?.flags || {};
  const lastEvent = stack?.last_event || {};
  const lastReact = stack?.last_reactivation || {};
  const action = (frame?.agents_views?.[agentId || ''] || frame)?.mind?.action
    || frame?.mind?.action
    || {};
  const selectedAction = action?.selected ?? frame?.overview_facts?.selected_action ?? '—';
  const actionSource = action?.source ?? stack?.selection_source ?? '—';

  const ctxId = persist?.active_id ? (stack?.last_active_context?.context_id || ctx?.last_active_id || ctx?.top?.[0]?.context_id) : (ctx?.last_active_id || ctx?.top?.[0]?.context_id);
  const ctxSupport = ctx?.top?.[0]?.support;
  const ctxReuse = lastReact?.status || (ctx?.reactivation_events != null ? `react×${ctx.reactivation_events}` : null);
  const depth = prosp?.last_depth ?? persist?.depth;
  const age = persist?.age;
  const supportStatus = persist?.support_status;
  const novel = Boolean(persist?.novel_composition);
  const persistActive = Boolean(persist?.active_id) && String(supportStatus || '').toUpperCase() !== 'COLLAPSED';

  const interpretation = useMemo(() => {
    const bits: string[] = [];
    if (flags.contextual_predictive_organization) {
      if (lastReact?.status === 'MATCH') bits.push('context reused');
      else if (ctx?.formation_events) bits.push('contextual organization enabled');
    }
    if (novel) bits.push('new prospective composition');
    if (persistActive) bits.push('prospective control persisting');
    if (String(lastEvent?.type || '').toUpperCase() === 'INTERRUPT') bits.push('prospective control interrupted');
    if (persistActive) bits.push('intention-like control active');
    return bits;
  }, [flags, lastReact, ctx, novel, persistActive, lastEvent]);

  // Bounded event strip (frontend only; compact labels)
  const [hist, setHist] = useState<HistEvt[]>([]);
  const prevKey = useRef('');
  useEffect(() => {
    const labels: string[] = [];
    if (lastReact?.status === 'MATCH' || lastReact?.status === 'WEAK') labels.push('CTX REACTIVATED');
    if (String(lastEvent?.type || '') === 'SELECT') labels.push('PSC/SELECT→PERSIST');
    if (String(lastEvent?.type || '') === 'CONTINUE') labels.push('PERSIST');
    if (String(lastEvent?.type || '') === 'INTERRUPT') labels.push('INTERRUPT');
    if (String(lastEvent?.type || '') === 'COMPLETE') labels.push('COMPLETE');
    if (!labels.length) return;
    const key = `${tick}:${labels.join('|')}:${persist?.active_id || ''}:${lastEvent?.type || ''}`;
    if (key === prevKey.current) return;
    prevKey.current = key;
    setHist((h) => {
      const next = [...h, ...labels.map((label) => ({ tick, label, key: `${key}:${label}` }))];
      return next.slice(-HISTORY_CAP);
    });
  }, [tick, lastReact, lastEvent, persist?.active_id]);

  // Reset history on agent switch
  useEffect(() => {
    setHist([]);
    prevKey.current = '';
  }, [agentId]);

  if (!stack && !flags.contextual_predictive_organization && !flags.context_grounded_prospection && !flags.persistent_prospective_control) {
    return (
      <div className="panel">
        <h3>CONTEXT → PROSPECTION → CONTROL</h3>
        <div className="subtle">4.26–4.28 disabled. Enable under Predictive / PSC.</div>
      </div>
    );
  }

  const pipelineActive = {
    ctx: Boolean(flags.contextual_predictive_organization) && Boolean(ctxId || ctx?.n_contexts),
    prosp: Boolean(flags.context_grounded_prospection) && (Number(prosp?.n_transitions) > 0 || depth != null),
    psc: String(stack?.psc_mode || '').toUpperCase() === 'SCENARIO_COMPETITION',
    persist: persistActive,
    motor: selectedAction != null && selectedAction !== '—',
  };

  return (
    <div className="panel">
      <h3 title="Scientific Observer chain for 4.26–4.28. No PLACE/MAP/GOAL/INTENTION variables in cognition.">
        CONTEXT → PROSPECTION → CONTROL
      </h3>
      <div className="subtle" style={{ marginBottom: 8 }}>
        Observer reconstruction of contextual compression → prospection → persistent control.
        Cognition has no semantic INTENTION / PLACE / MAP variables.
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'stretch', marginBottom: 10 }}>
        <div style={stageStyle(pipelineActive.ctx)} title="Reusable higher-order predictive organization formed from repeated relational experience.">
          <div className="subtle">CONTEXT</div>
          <div><strong>{ctxId || (flags.contextual_predictive_organization ? 'READY' : 'OFF')}</strong></div>
          <div className="subtle">
            {ctxSupport != null ? `support ${ctxSupport}` : (ctx?.n_contexts != null ? `n=${ctx.n_contexts}` : '—')}
            {ctxReuse ? ` · ${ctxReuse}` : ''}
          </div>
        </div>
        <div className="subtle" style={{ alignSelf: 'center' }}>→</div>
        <div style={stageStyle(pipelineActive.prosp)} title="Prospective composition using learned higher-order contextual structures.">
          <div className="subtle">PROSPECTION</div>
          <div><strong>{depth != null ? `depth ${depth}` : (flags.context_grounded_prospection ? 'READY' : 'OFF')}</strong></div>
          <div className="subtle">transitions {prosp?.n_transitions ?? '—'}</div>
        </div>
        <div className="subtle" style={{ alignSelf: 'center' }}>→</div>
        <div style={stageStyle(pipelineActive.psc)} title="Prospective Scenario Competition">
          <div className="subtle">PSC</div>
          <div><strong>{pipelineActive.psc ? 'SCENARIO' : '—'}</strong></div>
          <div className="subtle">{String(actionSource || '').slice(0, 28)}</div>
        </div>
        <div className="subtle" style={{ alignSelf: 'center' }}>→</div>
        <div
          style={stageStyle(pipelineActive.persist || String(lastEvent?.type) === 'INTERRUPT')}
          title="A selected prospective continuation may remain causally relevant across subsequent actions while predictive support persists."
        >
          <div className="subtle">PERSIST</div>
          <div>
            <strong>
              {String(lastEvent?.type) === 'INTERRUPT'
                ? 'INTERRUPTED'
                : persistActive
                  ? `ACTIVE · age ${age ?? 0}`
                  : (flags.persistent_prospective_control ? 'READY' : 'OFF')}
            </strong>
          </div>
          <div className="subtle">
            {persist?.active_id || '—'}
            {supportStatus ? ` · ${supportStatus}` : ''}
          </div>
        </div>
        <div className="subtle" style={{ alignSelf: 'center' }}>→</div>
        <div style={stageStyle(pipelineActive.motor)}>
          <div className="subtle">MOTOR</div>
          <div><strong>{String(selectedAction)}</strong></div>
          <div className="subtle">{String(actionSource || '').slice(0, 28)}</div>
        </div>
      </div>

      {persistActive && (
        <div className="flag" style={{ marginBottom: 8 }} title="Same prospective structure remaining causally active across ticks">
          ACTIVE FOR {Number(age ?? 0)} TICK{Number(age ?? 0) === 1 ? '' : 'S'}
          {novel ? ' · NOVEL COMPOSITION' : ''}
        </div>
      )}
      {String(lastEvent?.type) === 'INTERRUPT' && (
        <div className="flag pending" style={{ marginBottom: 8 }}>
          INTERRUPTED · predictive mismatch
          {lastEvent?.id ? ` · was ${lastEvent.id}` : ''}
          {lastEvent?.age != null ? ` · age ${lastEvent.age}` : ''}
        </div>
      )}

      {interpretation.length > 0 && (
        <div className="subtle" style={{ marginBottom: 8 }} title="Observer-level description only. Never sent into cognition.">
          <strong>Observer interpretation:</strong> {interpretation.join(' · ')}
          {interpretation.includes('intention-like control active') && (
            <span title="Observer-level description of persistent prospective control. No semantic INTENTION variable exists in cognition.">
              {' '}(intention-like = Observer label only)
            </span>
          )}
        </div>
      )}

      <div className="subtle" style={{ marginBottom: 4 }}>Recent events (bounded)</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {hist.length === 0 && <span className="na">—</span>}
        {hist.map((e, i) => (
          <span key={`${e.key}-${i}`} className="flag" style={{ fontSize: 10 }}>
            t{e.tick} {e.label}
          </span>
        ))}
      </div>

      {isFull && (
        <div style={{ borderTop: '1px solid var(--line)', paddingTop: 8 }}>
          <div className="section-label">FULL / diagnostic</div>
          {full.ppc?.active && (
            <div className="subtle" style={{ marginBottom: 4 }}>
              Prospective structure: {(full.ppc.active.path_ids || []).join(' → ') || full.ppc.active.id}
              {' · '}actions: {(full.ppc.active.actions || []).join(' → ')}
              {full.ppc.active.novel_composition ? ' · NOVEL COMPOSITION' : ''}
            </div>
          )}
          {full.cgp?.last_composition && (
            <div className="subtle">Last composition: {JSON.stringify(full.cgp.last_composition)}</div>
          )}
          {full.cpo?.last_reactivation && (
            <div className="subtle">Last reactivation: {JSON.stringify(full.cpo.last_reactivation)}</div>
          )}
          <div className="subtle">Motor chunks: {full.ppc?.n_motor_chunks ?? persist?.n_motor_chunks ?? 0}</div>
        </div>
      )}
    </div>
  );
}

export default ContextualProspectiveControlPanel;
