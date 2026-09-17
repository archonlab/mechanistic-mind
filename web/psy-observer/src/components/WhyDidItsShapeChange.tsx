export function WhyDidItsShapeChange({ whyMove, physical }: { whyMove: any; physical?: any }) {
  const shape = whyMove?.why_did_its_shape_change || physical?.deformation;
  if (!shape || shape.status === 'DISABLED' || shape.enabled === false) {
    return <div className="availability">body_deformation OFF or no sample</div>;
  }
  const fmt = (v: any) => Array.isArray(v) ? `${v.length} sites` : (v == null ? '—' : String(v));
  return (
    <div>
      <div className="metric"><span>Source</span><strong>{String(shape.shape_change_source || '—')}</strong></div>
      <div className="metric"><span>Requested work</span><strong>{fmt(shape.actuator_work ?? shape.work_requested)}</strong></div>
      <div className="metric"><span>Allocated / supplied</span><strong>{fmt(shape.reservoir_work_supplied)}</strong></div>
      <div className="metric"><span>Stored potential</span><strong>{fmt(shape.potential_after)}</strong></div>
      <div className="metric"><span>Viscous loss</span><strong>{fmt(shape.dissipated_viscous)}</strong></div>
      <div className="metric"><span>Geometry coupling</span><strong>{String(shape.geometry_coupling_enabled)}</strong></div>
      <div className="subtle">{(shape.chain || ['LOCAL_MATERIAL_STATE', 'DEFORMATION_STATE', 'BODY_LOCAL_GEOMETRY']).join(' → ')}</div>
    </div>
  );
}
