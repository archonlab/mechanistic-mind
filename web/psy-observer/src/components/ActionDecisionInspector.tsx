type Props = { why: any; summary?: string };

function scenLabel(s: any): string {
  if (!s) return '—';
  const id = s.scenario_id || '?';
  const d = s.depth ?? '?';
  const sup = s.historical_support ?? s.historical_support_raw ?? '?';
  const rel = typeof s.reliability === 'number' ? s.reliability.toFixed(2) : (s.reliability ?? '?');
  return `${id} d=${d} support=${sup} rel=${rel}`;
}

export function ActionDecisionInspector({ why, summary }: Props) {
  if (!why || why.status !== 'AVAILABLE') {
    return <div className="availability">{why?.status || 'CAUSAL ATTRIBUTION NOT AVAILABLE'}: {why?.reason || ''}</div>;
  }

  const available: string[] = why.available_physical_actions || (why.candidates || []).map((c: any) => c.candidate) || [];
  const supported: string[] = why.supported_physical_actions || [];
  const groups = why.scenario_groups || {};
  const competition = why.competition || {};
  const selected = why.selected;
  const mode = why.prospective_selection_mode || competition.mode || 'UNKNOWN';

  return (
    <div>
      {summary && (
        <div className="kv" style={{ marginBottom: 8, whiteSpace: 'pre-wrap' }}>
          {summary}
        </div>
      )}

      <div className="muted" style={{ fontSize: 11, margin: '6px 0' }}>
        CURRENT STATE → SUPPORTED PROSPECTIVE SCENARIOS → SCENARIO COMPETITION → SELECTED ACTION → ACTION BRIDGE → PHYSICAL CONSEQUENCE
      </div>

      <div className="row"><span>MODE</span><span>{String(mode)}</span></div>
      <div className="row"><span>SELECTED</span><strong>{String(selected)}</strong></div>
      <div className="row"><span>SOURCE</span><span>{String(why.source)}</span></div>

      <div className="section-label">Distinctions</div>
      <div className="kv">AVAILABLE: {available.join(', ') || '—'}</div>
      <div className="kv">SUPPORTED: {supported.length ? supported.join(', ') : '(none)'}</div>
      <div className="kv">SELECTED: {String(selected)}</div>
      <div className="kv" style={{ opacity: 0.85 }}>
        AVAILABLE ≠ SUPPORTED ≠ SELECTED (physical availability is not predictive support)
      </div>

      <div className="section-label">Supported prospective scenarios</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, fontSize: 11 }}>
        {available.map((act) => {
          const g = groups[act] || {};
          const scenarios = g.scenarios || g.front || [];
          const isSupported = !!g.supported || (scenarios && scenarios.length > 0) || supported.includes(act);
          const isSelected = act === selected;
          return (
            <div
              key={act}
              style={{
                border: '1px solid #334155',
                borderLeft: isSelected ? '3px solid #22c55e' : isSupported ? '3px solid #38bdf8' : '3px solid #475569',
                padding: 6,
                minHeight: 64,
              }}
            >
              <div><strong>{act}</strong></div>
              <div className="muted">{isSelected ? 'SELECTED' : isSupported ? 'SUPPORTED' : 'UNSUPPORTED'}</div>
              {!isSupported || !scenarios.length ? (
                <div>—</div>
              ) : (
                scenarios.slice(0, 4).map((s: any, i: number) => (
                  <div key={s.scenario_id || i}>{scenLabel(s)}</div>
                ))
              )}
            </div>
          );
        })}
      </div>

      <div className="section-label">Scenario competition</div>
      <div className="metric"><span>Evidence</span><strong>{(competition.evidence_dimensions || []).join(' → ') || 'NOT AVAILABLE'}</strong></div>
      <div className="metric"><span>Order</span><strong>{competition.evidence_order || 'NOT AVAILABLE'}</strong></div>
      <div className="metric"><span>Outcome</span><strong>{competition.outcome_class || competition.selection_reason || 'NOT AVAILABLE'}</strong></div>
      <div className="metric"><span>Selection reason</span><strong>{competition.selection_reason || '—'}</strong></div>
      <div className="metric"><span>Tie resolution</span><strong>{String(competition.tie_resolution ?? why.tie_break_rule ?? '—')}</strong></div>
      <div className="subtle">Unsupported: {(competition.unsupported_actions || []).join(', ') || 'none'}</div>
      <div className="subtle">Ties: {(competition.ties || []).length || 0} · Incomparable: {(competition.incomparable_candidates || []).length || 0}</div>
      {competition.selected_scenario && (
        <div className="subtle">Selected scenario: {scenLabel(competition.selected_scenario)}</div>
      )}

      <div className="section-label">Selection rule</div>
      <div className="kv">{why.selection_rule || 'SELECTION DIFFERENCE NOT EXPOSED'}</div>
      <div className="kv">peer_evaluation: {why.peer_evaluation || 'NOT_AVAILABLE'}</div>
      <div className="kv">tie_state: {why.tie_state || 'NOT_AVAILABLE'}</div>

      <div className="section-label">Candidates (availability vs support)</div>
      <div className="list">
        {(why.candidates || []).map((c: any) => (
          <div
            key={c.candidate}
            className="kv"
            style={{ borderLeft: c.accepted ? '3px solid #22c55e' : '3px solid #334155', paddingLeft: 8 }}
          >
            <div>
              <strong>{c.candidate}</strong> {c.accepted ? '← SELECTED' : ''}
            </div>
            <div>syntactically_available: {String(c.syntactically_available)}</div>
            <div>predictively_supported: {String(c.predictively_supported)}</div>
            <div>scenario_count: {c.scenario_count ?? '—'}</div>
            <div>prospective_roots: {c.prospective_root_count}</div>
            <div>compression: {c.compression_match ? 'matched' : 'none'}</div>
            <div>rejection: {c.rejection_reason || '—'}</div>
          </div>
        ))}
      </div>

      <div className="section-label">Action bridge</div>
      <div className="metric"><span>Cognitive action</span><strong>{String(why.bridge?.cognitive_action || why.selected)}</strong></div>
      <div className="metric"><span>Physical received</span><strong>{String(why.bridge?.physical_action_received || '—')}</strong></div>
      <div className="subtle">Bridge details remain in Advanced / Raw.</div>

      <div className="section-label">Physical consequence</div>
      <div className="metric"><span>Status</span><strong>{String(why.consequence?.status || '—')}</strong></div>
      <div className="metric"><span>dx / dy</span><strong>{String(why.consequence?.dx ?? '—')} / {String(why.consequence?.dy ?? '—')}</strong></div>
      <div className="subtle">Movement is explained in Why did it move? Physical work constraint is not a change of mind.</div>
    </div>
  );
}
