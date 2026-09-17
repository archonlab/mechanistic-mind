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

export function WhyDidItRotate({ whyMove, physical }: Props) {
  const orient = physical?.orientation || whyMove?.orientation || {};
  const rot = whyMove?.why_did_it_rotate || orient.receipt || orient.meta || {};
  const enabled = Boolean(orient.enabled ?? rot?.enabled ?? whyMove?.orientation?.enabled);
  if (!whyMove || whyMove.status !== 'AVAILABLE') {
    return <div className="availability">NOT AVAILABLE</div>;
  }
  if (!enabled) {
    return <div className="availability">body_orientation mode OFF</div>;
  }
  return (
    <div>
      <div className="metric"><span>theta</span><strong>{fmt(orient.theta ?? rot.theta)}</strong></div>
      <div className="metric"><span>omega</span><strong>{fmt(orient.omega ?? rot.omega)}</strong></div>
      <div className="metric"><span>net torque</span><strong>{fmt(orient.torque ?? rot.tau)}</strong></div>
      <div className="metric"><span>motor torque</span><strong>{fmt(orient.motor_torque ?? 0)}</strong></div>
      <div className="metric"><span>action torque</span><strong>{fmt(orient.action_torque ?? 0)}</strong></div>
      <div className="metric"><span>net force</span><strong>{fmt(rot.net_force)}</strong></div>
      <div className="subtle">Center-applied motor and discrete action currently contribute no torque.</div>
    </div>
  );
}
