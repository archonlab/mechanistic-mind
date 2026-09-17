type Props = {
  events: any[];
  activeTick?: number;
  onSelect: (tick: number) => void;
};

export function TimelinePanel({ events, activeTick, onSelect }: Props) {
  return (
    <div className="panel">
      <h3>Timeline (bounded buffer)</h3>
      <div className="timeline-bar">
        {events.map((e) => (
          <div
            key={`${e.tick}-${e.action}`}
            className={`tick-mark ${e.action && e.action !== 'WAIT' ? 'action' : ''} ${e.tick === activeTick ? 'active' : ''}`}
            title={`t=${e.tick} ${e.action || ''}`}
            onClick={() => onSelect(Number(e.tick))}
          />
        ))}
      </div>
      <div className="kv" style={{ maxHeight: 120, overflow: 'auto' }}>
        {events.slice(-12).map((e) => `t=${e.tick} action=${e.action} src=${e.action_source || '—'}`).join('\n') || 'no events'}
      </div>
    </div>
  );
}
