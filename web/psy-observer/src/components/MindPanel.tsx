type Props = { mind: any };
export function MindPanel({ mind }: Props) {
  if (!mind) return <div className="panel"><h3>Mind</h3><div className="na">NOT AVAILABLE</div></div>;
  return (
    <div className="panel">
      <h3>Mind — active mechanisms</h3>
      <div className="list">
        {(mind.mechanisms || []).map((m: any) => (
          <div className="row" key={m.name}>
            <span>{m.name}</span>
            <span className="badge">{m.state}{m.physical_path ? ` · ${m.physical_path}` : ''}</span>
          </div>
        ))}
      </div>
      <h3 style={{ marginTop: 12 }}>Bridges</h3>
      <div className="kv">{JSON.stringify(mind.bridges || {}, null, 2)}</div>
      <h3 style={{ marginTop: 12 }}>Metrics</h3>
      <div className="kv">{JSON.stringify(mind.metrics || {}, null, 2)}</div>
    </div>
  );
}
