import { useCallback, useEffect, useState } from 'react';
import {
  experimenterCapture,
  experimenterCommand,
  experimenterListCaptures,
  experimenterRemove,
  experimenterSetMobility,
  experimenterSetTarget,
  experimenterSpawn,
  experimenterTestCapture,
  listSignalSpecimens,
} from '../api/client';

type ExpState = {
  status?: string;
  body_id?: string;
  last_requested?: string | null;
  last_realized?: Record<string, unknown> | null;
  intervention_active?: boolean;
  intervention_ever?: boolean;
  recent_events?: Array<Record<string, unknown>>;
  target?: Record<string, unknown> | null;
  captures?: Array<{ capture_id: string; start_tick: number; end_tick: number }>;
  queue_len?: number;
  mobility_mode?: string;
  research_supply?: Record<string, unknown> | null;
};

export function InteractPanel({
  live,
  onRefresh,
  /** Display-only: last key from global App-shell listener (no second handler here). */
  globalPressed,
}: {
  live?: ExpState | null;
  onRefresh?: () => void;
  globalPressed?: string | null;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [specimens, setSpecimens] = useState<Array<Record<string, unknown>>>([]);
  const [selectedSpecimen, setSelectedSpecimen] = useState<string>('');
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const [cameraFollow, setCameraFollow] = useState<'FREE' | 'YOU' | 'TARGET'>('FREE');

  const st = live || {};
  const active = st.status === 'CONTROL_ACTIVE';

  const refreshSpecimens = useCallback(async () => {
    try {
      const data = await listSignalSpecimens({ limit: 32 });
      setSpecimens((data.specimens || []) as Array<Record<string, unknown>>);
    } catch {
      setSpecimens([]);
    }
  }, []);

  useEffect(() => { refreshSpecimens(); }, [refreshSpecimens]);

  /** UI buttons only — keyboard is owned exclusively by App useExperimenterKeyboard. */
  const sendCmd = useCallback(async (kind: string, action?: string) => {
    if (!active) return;
    try {
      const out = await experimenterCommand({ kind, action });
      if (!out.accepted) setMsg(String(out.error || 'command rejected'));
    } catch (e) {
      setMsg(String(e));
    }
  }, [active]);

  async function spawn(near?: number) {
    setBusy('spawn');
    setMsg(null);
    try {
      const out = await experimenterSpawn(near != null ? { near_agent: near } : {});
      setMsg(out.accepted ? 'SPAWNED · INTERVENTION ACTIVE' : String(out.error));
      onRefresh?.();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy('remove');
    try {
      const out = await experimenterRemove();
      setMsg(out.accepted ? 'REMOVED · intervention provenance retained' : String(out.error));
      onRefresh?.();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function capture() {
    setBusy('capture');
    try {
      const out = await experimenterCapture();
      setMsg(out.accepted ? `CAPTURED ${out.capture?.capture_id}` : String(out.error));
      onRefresh?.();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function testLast() {
    setBusy('test');
    try {
      const list = await experimenterListCaptures();
      const caps = list.captures || [];
      if (!caps.length) {
        setMsg('no captures');
        return;
      }
      const id = caps[caps.length - 1].capture_id;
      const out = await experimenterTestCapture(id, 40);
      setTestResult(out);
      setMsg(
        out.accepted
          ? `TEST · SOURCE_CONTEXT_DEPENDENCE=${out.factorial?.SOURCE_CONTEXT_DEPENDENCE}`
          : String(out.error || out.factorial?.error),
      );
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function replaySpecimen() {
    if (!selectedSpecimen) return;
    setBusy('replay');
    try {
      const out = await experimenterCommand({
        kind: 'SPECIMEN_REPLAY',
        specimen_id: selectedSpecimen,
      });
      setMsg(out.accepted ? `NATURAL REPLAY ${selectedSpecimen}` : String(out.error));
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  }

  const realized = st.last_realized || {};
  const events = st.recent_events || [];

  return (
    <div className="panel interact-lab" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="metric">
        <span>INTERACTION LAB</span>
        <strong>EXPERIMENTER-CONTROLLED TIKTAALIK</strong>
      </div>
      <div className="subtle">
        Ordinary physical body · experimenter-selected actions · no privileged cognition identity.
        Manual interaction is exploratory — not causal.
      </div>

      {(st.intervention_active || st.intervention_ever) && (
        <div className="control-receipt warn-banner">
          INTERVENTION ACTIVE{st.intervention_ever && !active ? ' (body removed — provenance retained)' : ''}
        </div>
      )}

      <div className="metric">
        <span>Status</span>
        <strong>{st.status || 'NOT_SPAWNED'}</strong>
      </div>

      <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <button className="active" disabled={!!busy || active} onClick={() => spawn()}>
          SPAWN CONTROLLED TIKTAALIK
        </button>
        <button disabled={!!busy || active} onClick={() => spawn(1)}>SPAWN NEAR AGENT_1</button>
        <button disabled={!!busy || !active} onClick={remove}>REMOVE</button>
      </div>

      <div className="panel" style={{ padding: 8 }}>
        <div className="metric"><span>CONTROLLED BODY</span><strong>{st.body_id || '—'}</strong></div>
        <div className="metric"><span>REQUESTED</span><strong>{st.last_requested || globalPressed || '—'}</strong></div>
        <div className="metric">
          <span>REALIZED</span>
          <strong>
            x={fmt(realized.x)} y={fmt(realized.y)} · spd={fmt(realized.speed)} · θ={fmt(realized.theta)}
          </strong>
        </div>
        <div className="metric"><span>QUEUE</span><strong>{st.queue_len ?? 0}</strong></div>
      </div>

      <div className="panel" style={{ padding: 8 }}>
        <div className="metric"><span>EXPERIMENTER MOBILITY</span><strong>{st.mobility_mode || 'ORDINARY_WORK'}</strong></div>
        <div className="subtle">
          RESEARCH MOBILITY = external work supply before ordinary allocation.
          Not eating. Ordinary action → physics path preserved. No teleport/noclip.
        </div>
        <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button
            className={(st.mobility_mode || 'ORDINARY_WORK') === 'ORDINARY_WORK' ? 'active' : ''}
            disabled={!active || !!busy}
            onClick={async () => {
              await experimenterSetMobility('ORDINARY_WORK');
              onRefresh?.();
            }}
          >
            ORDINARY WORK
          </button>
          <button
            className={st.mobility_mode === 'RESEARCH_MOBILITY' ? 'active' : ''}
            disabled={!active || !!busy}
            onClick={async () => {
              await experimenterSetMobility('RESEARCH_MOBILITY');
              onRefresh?.();
            }}
          >
            RESEARCH MOBILITY
          </button>
        </div>
        {st.mobility_mode === 'RESEARCH_MOBILITY' && (
          <div className="subtle">
            WORK SOURCE · EXPERIMENTER_RESEARCH_SUPPLY
            {st.research_supply && typeof st.research_supply.credited === 'number'
              ? ` · last +${Number(st.research_supply.credited).toFixed(3)}`
              : ''}
          </div>
        )}
      </div>

      <div className="subtle">
        Keyboard is global (any Observer tab) while CONTROL ACTIVE:
        W/A/S/D move · Space WAIT · Q FIELD_A · E FIELD_B —
        requests only; physics realizes. Key-repeat suppressed. Typing fields ignored.
      </div>

      <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
        {(['MOVE:N', 'MOVE:S', 'MOVE:W', 'MOVE:E', 'WAIT'] as const).map(a => (
          <button key={a} disabled={!active} onClick={() => sendCmd('ACTION', a)}>{a}</button>
        ))}
        <button disabled={!active} onClick={() => sendCmd('FIELD_A')}>FIELD_A</button>
        <button disabled={!active} onClick={() => sendCmd('FIELD_B')}>FIELD_B</button>
      </div>

      <div className="panel" style={{ padding: 8 }}>
        <div className="metric"><span>SIGNAL LIBRARY</span><strong>NATURAL SPECIMEN REPLAY</strong></div>
        <div className="toolbar-row" style={{ gap: 8 }}>
          <select
            value={selectedSpecimen}
            onChange={e => setSelectedSpecimen(e.target.value)}
            style={{ minWidth: 180 }}
          >
            <option value="">— select specimen —</option>
            {specimens.map(s => (
              <option key={String(s.specimen_id)} value={String(s.specimen_id)}>
                {String(s.specimen_id)} · {String(s.channel || '?')}
              </option>
            ))}
          </select>
          <button disabled={!active || !selectedSpecimen || !!busy} onClick={replaySpecimen}>
            REPLAY FROM BODY
          </button>
          <button onClick={refreshSpecimens}>↻</button>
        </div>
        <div className="subtle">No semantic labels. Physical footprint replay only.</div>
      </div>

      <div className="panel" style={{ padding: 8 }}>
        <div className="metric"><span>INTERACTION TARGET</span><strong>Observer-only</strong></div>
        <div className="toolbar-row" style={{ gap: 8 }}>
          <button onClick={() => experimenterSetTarget('agent_0').then(onRefresh)}>agent_0</button>
          <button onClick={() => experimenterSetTarget('agent_1').then(onRefresh)}>agent_1</button>
          <button onClick={() => experimenterSetTarget(null).then(onRefresh)}>clear</button>
        </div>
        {st.target && (
          <div className="subtle">
            {String(st.target.agent_id)} · dist={fmt(st.target.distance)} ·
            action={String(st.target.action)} · src={String(st.target.selection_source)} ·
            FIELD_A={fmt(st.target.field_A)} FIELD_B={fmt(st.target.field_B)}
          </div>
        )}
      </div>

      <div className="panel" style={{ padding: 8 }}>
        <div className="metric"><span>AUTONOMOUS RESPONSE</span><strong>observational only</strong></div>
        {st.target ? (
          <div className="subtle">
            CURRENT selection_source={String(st.target.selection_source)} ·
            requested_action={String(st.target.action)}
            {' · '}COGNITIVE STATE CHANGE: mark only after matched baseline (OBSERVATIONAL ONLY here)
          </div>
        ) : (
          <div className="subtle">Select an autonomous agent to compare local FIELD / selection / action.</div>
        )}
      </div>

      <div className="panel" style={{ padding: 8, maxHeight: 160, overflow: 'auto' }}>
        <div className="metric"><span>LIVE EVENT STRIP</span><strong>mechanistic</strong></div>
        {events.length === 0 && <div className="subtle">No events yet.</div>}
        {events.slice().reverse().map((ev, i) => (
          <div key={i} className="subtle">
            t{String(ev.tick)} · {String(ev.event_type)}
            {ev.action ? ` ${ev.action}` : ''}
            {ev.channel ? ` FIELD_${ev.channel}` : ''}
            {ev.with_body ? ` ${ev.with_body}` : ''}
          </div>
        ))}
      </div>

      <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <button className="active" disabled={!!busy} onClick={capture}>CAPTURE INTERACTION</button>
        <button disabled={!!busy} onClick={testLast}>TEST THIS INTERACTION</button>
      </div>
      <div className="subtle">
        CAPTURE → EXPLORATORY_HUMAN_INTERACTION · TEST → matched CONTROL / BODY_ONLY / FIELD_ONLY /
        BODY_PLUS_FIELD / SHAM · verdict SOURCE_CONTEXT_DEPENDENCE (not recognition).
      </div>

      {(st.captures || []).length > 0 && (
        <div className="subtle">
          Captures: {(st.captures || []).map(c => c.capture_id).join(', ')}
        </div>
      )}

      {testResult && (
        <div className="panel" style={{ padding: 8 }}>
          <div className="metric">
            <span>MATCHED TEST</span>
            <strong>{String((testResult.factorial as any)?.SOURCE_CONTEXT_DEPENDENCE || '—')}</strong>
          </div>
          <pre style={{ fontSize: 11, maxHeight: 120, overflow: 'auto' }}>
            {JSON.stringify(
              testResult.fingerprint
                || (testResult.factorial as Record<string, unknown> | undefined)?.arms
                || testResult,
              null,
              2,
            )}
          </pre>
        </div>
      )}

      <div className="toolbar-row" style={{ gap: 8 }}>
        <span className="subtle">Camera (Observer-only):</span>
        {(['FREE', 'YOU', 'TARGET'] as const).map(c => (
          <button key={c} className={cameraFollow === c ? 'active' : ''} onClick={() => setCameraFollow(c)}>
            {c === 'YOU' ? 'FOLLOW CONTROLLED' : c === 'TARGET' ? 'FOLLOW TARGET' : 'FREE'}
          </button>
        ))}
      </div>
      {/* cameraFollow is UI preference; map follow wiring is Observer-local */}
      <input type="hidden" value={cameraFollow} readOnly />

      {msg && <div className="control-receipt">{msg}</div>}
    </div>
  );
}

function fmt(v: unknown) {
  if (typeof v === 'number' && Number.isFinite(v)) return v.toFixed(2);
  return '—';
}
