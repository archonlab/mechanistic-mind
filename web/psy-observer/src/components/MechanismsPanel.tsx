type Props = { data: any; onToggle?: (id: string, enabled: boolean) => void };

export function MechanismsPanel({ data, onToggle }: Props) {
  if (!data) {
    return <div className="panel"><h3>Mechanisms</h3><div className="na">Load /api/mechanisms</div></div>;
  }
  const items = data.mechanisms || [];
  return (
    <div className="panel">
      <h3>Mechanisms</h3>
      <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
        Independently ablatable. Provenance preserved.
      </div>
      {items.map((m: any) => (
        <div key={m.id} style={{ borderBottom: '1px solid #333', padding: '8px 0' }}>
          <div className="row">
            <strong>{m.label}</strong>
            <button
              type="button"
              onClick={() => onToggle && onToggle(m.id, !(m.enabled))}
              style={{
                background: m.enabled ? '#166534' : '#444',
                color: '#fff',
                border: 'none',
                borderRadius: 4,
                padding: '2px 10px',
                cursor: 'pointer',
              }}
            >
              {m.enabled ? 'ON' : 'OFF'}
            </button>
          </div>
          <div className="muted" style={{ fontSize: 12 }}>{m.description}</div>
          <div className="kv" style={{ fontSize: 11 }}>{m.validation}</div>
        </div>
      ))}
      {data.force_contributions && (
        <div style={{ marginTop: 8 }}>
          <h3>Force contributions (last tick)</h3>
          <div className="kv" style={{ fontSize: 11 }}>{JSON.stringify(data.force_contributions, null, 2)}</div>
        </div>
      )}
    </div>
  );
}
