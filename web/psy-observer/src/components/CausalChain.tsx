type Props = { chain: any };

function Stage({ name, stage }: { name: string; stage: any }) {
  if (!stage) return (
    <div className="stage"><div className="name">{name}</div><div className="na">NOT AVAILABLE</div></div>
  );
  const status = stage.status || 'AVAILABLE';
  let body = '';
  if (status !== 'AVAILABLE') {
    body = status + (stage.reason ? `: ${stage.reason}` : '');
  } else if (name === 'WORLD') {
    const d = stage.data || {};
    body = `T_mean=${Number(d.T_mean).toFixed(4)}\ntick=${d.tick}`;
  } else if (name === 'PERCEPTION') {
    const d = stage.data || {};
    body = Object.entries(d).slice(0, 6).map(([k, v]) => `${k}=${Number(v).toFixed(3)}`).join('\n');
  } else if (name === 'BODY') {
    const d = stage.data || {};
    body = `x=${Number(d.x).toFixed(3)} y=${Number(d.y).toFixed(3)}\nT=${Number(d.T).toFixed(4)} mech=${Number(d.mech).toFixed(4)}`;
  } else if (name === 'INTERNAL') {
    const p = stage.physical || {};
    body = `c shape=${JSON.stringify(p.shape)}\nsum=${Number(p.sum).toFixed(6)}`;
  } else if (name === 'PREDICTION') {
    const n = (stage.prediction_matches || []).length;
    const c = (stage.continuations || []).length;
    body = `matches=${n}\ncontinuations=${c}`;
  } else if (name === 'ACTION') {
    body = `${stage.selected || '—'}\n${stage.source || ''}`;
  } else if (name === 'CONSEQUENCE') {
    body = `dx=${Number(stage.dx).toFixed(4)} dy=${Number(stage.dy).toFixed(4)}\ndT=${Number(stage.dT).toFixed(5)}`;
  } else {
    body = JSON.stringify(stage).slice(0, 120);
  }
  return (
    <div className="stage">
      <div className="name">{name}</div>
      {status !== 'AVAILABLE' ? <div className="na">{body}</div> : <div className="kv stage-body">{body}</div>}
    </div>
  );
}

export function CausalChain({ chain }: Props) {
  const stages = chain?.stages || {};
  return (
    <div className="chain">
      {['WORLD','PERCEPTION','BODY','INTERNAL','PREDICTION','ACTION','CONSEQUENCE'].map((k) => (
        <Stage key={k} name={k} stage={stages[k]} />
      ))}
    </div>
  );
}
