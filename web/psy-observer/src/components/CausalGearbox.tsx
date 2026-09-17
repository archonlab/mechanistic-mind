type Props = { data: any };

export function CausalGearbox({ data }: Props) {
  if (!data) {
    return <div className="panel"><h3>Causal Gearbox</h3><div className="na">Load diagnostics/gearbox</div></div>;
  }
  const baseline = data.baseline || {};
  const experimental = data.experimental || {};
  const live = data.live || {};
  const edges = (baseline.edges || []) as any[];
  const absent = (baseline.not_demonstrated || []) as any[];
  const added = (experimental.added_edges || []) as any[];
  return (
    <div className="panel">
      <h3>Causal Gearbox</h3>
      <div className="muted" style={{ fontSize: 11 }}>
        What turns what — baseline vs experimentally introduced edges. No inferred causation from simultaneous change.
      </div>
      {live.tick != null && (
        <div className="kv" style={{ marginTop: 6 }}>
          LIVE tick={live.tick} endo={live.changing?.endo_mode} morph={live.changing?.morph_mode} orient={live.changing?.orient_mode} θ={live.changing?.theta} τ={live.changing?.tau} action={String(live.changing?.selected_action)}
          {' '}| v={JSON.stringify(live.changing?.['body.vx_vy'])}
          {' '}| B_sum={live.changing?.body_B_sum}
          {' '}| c_l1={live.changing?.['internal.c_l1']}
          {' '}| motor_u={JSON.stringify(live.changing?.motor_u)}
        </div>
      )}
      <h3 style={{ marginTop: 8 }}>Baseline edges (LEVEL 2+)</h3>
      <div className="list">
        {edges.map((e, i) => (
          <div key={i} className="kv" style={{ borderLeft: '3px solid #38bdf8', paddingLeft: 6 }}>
            <strong>{e.from}</strong> → <strong>{e.to}</strong> [{e.kind}] L{e.level} {e.type || ''} {e.lag || ''}
          </div>
        ))}
      </div>
      <h3 style={{ marginTop: 8 }}>Baseline NOT DEMONSTRATED</h3>
      <div className="list">
        {absent.map((e, i) => (
          <div key={i} className="kv" style={{ borderLeft: '3px solid #f59e0b', paddingLeft: 6 }}>
            <strong>{e.from}</strong> ↛ <strong>{e.to}</strong> — {e.evidence || e.kind}
          </div>
        ))}
      </div>
      <h3 style={{ marginTop: 8 }}>Experimental additions</h3>
      <div className="list">
        {added.length === 0 ? <div className="na">none loaded</div> : added.map((e, i) => (
          <div key={i} className="kv" style={{ borderLeft: '3px solid #a78bfa', paddingLeft: 6 }}>
            <strong>{e.from}</strong> → <strong>{e.to}</strong> [{e.kind}] L{e.level} {e.lag || ''}
          </div>
        ))}
      </div>
      <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>
        Path inspector (conceptual): internal.c → body.B → [TERMINATION] — no baseline path to position.
        With experimental motor: internal.c → motor_u → velocity → position.
      </div>
    </div>
  );
}
