type Props = { whyMove: any; physical?: any };

function fmt(v: any): string {
  if (v == null) return '—';
  if (Array.isArray(v)) return `[${v.map((x) => fmt(x)).join(', ')}]`;
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(4);
  if (typeof v === 'object') {
    if ('dx' in v && 'dy' in v) return `[${fmt(v.dx)}, ${fmt(v.dy)}]`;
    const values = Object.values(v);
    if (values.length && values.every((x) => typeof x === 'number' || x == null)) {
      return `[${values.map((x) => fmt(x)).join(', ')}]`;
    }
    return Object.entries(v).map(([k, x]) => `${k}=${fmt(x)}`).join(', ');
  }
  return String(v);
}

export function MotionCausalInspector({ whyMove, physical }: Props) {
  if (!whyMove || whyMove.status !== 'AVAILABLE') {
    return <div className="availability">{whyMove?.status || 'NOT AVAILABLE'}: {whyMove?.reason || 'step to sample'}</div>;
  }
  const causes = whyMove.causes || [];
  const add = whyMove.mechanical_decomposition?.additive_acceleration || {};
  const action = physical?.action || {};
  const motor = physical?.motor || {};
  const env = physical?.force_contributions?.environmental_site;
  return (
    <div>
      <div className="subtle">Physical causation. Separate from cognitive selection.</div>
      <div className="metric"><span>Selected action</span><strong>{String(whyMove.selected_action)}</strong></div>
      <div className="metric"><span>Position change</span><strong>{fmt(whyMove.position_change)}</strong></div>
      <div className="metric"><span>Environment</span><strong>{fmt(env || [add.ax_flow, add.ay_flow])}</strong></div>
      <div className="metric"><span>Inertia / drag</span><strong>{fmt([add.ax_drag, add.ay_drag])}</strong></div>
      <div className="metric"><span>Motor requested Δv</span><strong>{fmt(motor.motor_delta_v_requested)}</strong></div>
      <div className="metric"><span>Motor realized Δv</span><strong>{fmt(motor.motor_delta_v_realized)}</strong></div>
      <div className="metric"><span>Action requested Δv</span><strong>{fmt(action.action_dv_requested)}</strong></div>
      <div className="metric"><span>Action realized Δv</span><strong>{fmt(action.action_dv_realized)}</strong></div>
      <div className="subtle">Causes: {causes.length ? causes.join(', ') : 'NONE'}</div>
      <div className="subtle">WAIT can coexist with movement from environment, inertia, or motor.</div>
    </div>
  );
}
