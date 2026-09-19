/** Observer-only geometry interpretation panel (BETA2-GEO-01). */
export function GeometryPanel({ geometry }: { geometry: any }) {
  if (!geometry || typeof geometry !== 'object') {
    return (
      <div className="science-card">
        <h3>Geometry interpretation</h3>
        <div className="na">NOT AVAILABLE</div>
        <div className="subtle">Observer-only · not agent perception</div>
      </div>
    );
  }
  const agents = Array.isArray(geometry.agents) ? geometry.agents : [];
  return (
    <div className="science-card">
      <h3>Geometry interpretation</h3>
      <div className="subtle">
        Observer-only physical geometry · tick {geometry.tick ?? '—'} ·{' '}
        {geometry.honesty?.structure || 'emergent flow / soft contact'}
      </div>
      <div className="subtle">
        No semantic terrain labels · not provided to cognition
      </div>
      {agents.map((a: any) => {
        const flow = a.local_flow || {};
        const since = a.since_prev_capture || null;
        const req = a.requested_unit;
        return (
          <div key={a.agent_id} style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #334155' }}>
            <b>{a.agent_id}</b> · action {a.action || '—'} · ({Number(a.x).toFixed(2)}, {Number(a.y).toFixed(2)})
            <div className="kv">
              requested dir:{' '}
              {req && req.length === 2
                ? `(${Number(req[0]).toFixed(2)}, ${Number(req[1]).toFixed(2)})`
                : '—'}
            </div>
            <div className="kv">
              local flow:{' '}
              {flow.status === 'AVAILABLE'
                ? `(${Number(flow.vx).toFixed(3)}, ${Number(flow.vy).toFixed(3)}) |${Number(flow.mag).toFixed(3)}|`
                : flow.status || 'NOT AVAILABLE'}
            </div>
            {since ? (
              <div className="kv">
                since prev capture: Δ=({Number(since.dx).toFixed(3)}, {Number(since.dy).toFixed(3)})
                {' · '}align={since.action_alignment == null ? '—' : Number(since.action_alignment).toFixed(2)}
                {' · '}{since.outcome}
              </div>
            ) : (
              <div className="subtle">since prev capture: NOT AVAILABLE</div>
            )}
          </div>
        );
      })}
      {geometry.flow_overlay?.status === 'AVAILABLE' ? (
        <div className="subtle" style={{ marginTop: 8 }}>
          Flow overlay vectors: {geometry.flow_overlay.n} (PAUSED/full detail)
        </div>
      ) : null}
    </div>
  );
}
