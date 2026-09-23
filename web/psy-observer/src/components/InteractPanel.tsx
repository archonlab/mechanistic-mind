import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
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
import { InspectorAccordion } from '../inspectors/primitives';
import { cameraFollowStore } from '../observer/stores';

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
  layoutTab,
}: {
  live?: ExpState | null;
  onRefresh?: () => void;
  globalPressed?: string | null;
  layoutTab?: string;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [specimens, setSpecimens] = useState<Array<Record<string, unknown>>>([]);
  const [selectedSpecimen, setSelectedSpecimen] = useState<string>('');
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const cameraFollow = useSyncExternalStore(
    cameraFollowStore.subscribe,
    cameraFollowStore.get,
    cameraFollowStore.get,
  );

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
      if (out.accepted) {
        setMsg('SPAWNED · INTERVENTION ACTIVE');
      } else {
        const err = String(out.error || 'SPAWN_REJECTED:UNKNOWN');
        const detail = out.detail ? ` · ${out.detail}` : '';
        setMsg(err.startsWith('SPAWN_REJECTED') ? `${err}${detail}` : `SPAWN_REJECTED:${err}${detail}`);
      }
      onRefresh?.();
    } catch (e) {
      setMsg(`SPAWN_REJECTED:RUNTIME_UNAVAILABLE · ${String(e)}`);
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
  const show = (id: string) => !layoutTab || layoutTab === id;
  const spawnWhy = active ? 'Already in world — Remove first' : undefined;
  const moveWhy = !active ? 'Spawn controlled Tiktaalik first' : undefined;

  return (
    <div className="interact-lab" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
      {msg ? <div className={String(msg).includes('REJECTED') ? 'bad' : 'subtle'}>{msg}</div> : null}

      {show('agent') && (
        <InspectorAccordion id="exp-spawn" title="Spawn" defaultOpen>
          <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <button className="active" disabled={!!busy || active} title={spawnWhy} onClick={() => spawn()}>
              SPAWN CONTROLLED TIKTAALIK
            </button>
            <button disabled={!!busy || active} title={spawnWhy} onClick={() => spawn(0)}>SPAWN NEAR AGENT_0</button>
            <button disabled={!!busy || active} title={spawnWhy} onClick={() => spawn(1)}>SPAWN NEAR AGENT_1</button>
            <button disabled={!!busy || !active} title={!active ? 'Nothing to remove' : undefined} onClick={remove}>REMOVE</button>
          </div>
          <div className="metric"><span>CONTROLLED BODY</span><strong>{st.body_id || '—'}</strong></div>
          <div className="metric"><span>REQUESTED</span><strong>{st.last_requested || globalPressed || '—'}</strong></div>
          <div className="metric">
            <span>REALIZED</span>
            <strong>
              x={fmt(realized.x)} y={fmt(realized.y)} · spd={fmt(realized.speed)} · θ={fmt(realized.theta)}
            </strong>
          </div>
          <div className="metric"><span>QUEUE</span><strong>{st.queue_len ?? 0}</strong></div>
          <div className="metric"><span>EXPERIMENTER MOBILITY</span><strong>{st.mobility_mode || 'ORDINARY_WORK'}</strong></div>
          <div className="subtle">
            RESEARCH MOBILITY = external work supply before ordinary allocation.
            Not eating. Ordinary action → physics path preserved. No teleport/noclip.
          </div>
          <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <button
              className={(st.mobility_mode || 'ORDINARY_WORK') === 'ORDINARY_WORK' ? 'active' : ''}
              disabled={!active || !!busy}
              title={moveWhy}
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
              title={moveWhy}
              onClick={async () => {
                await experimenterSetMobility('RESEARCH_MOBILITY');
                onRefresh?.();
              }}
            >
              RESEARCH MOBILITY
            </button>
          </div>
        </InspectorAccordion>
      )}

      {show('movement') && (
        <InspectorAccordion id="exp-move" title="Manual control" defaultOpen>
          <div className="subtle">
            Keyboard is global while CONTROL ACTIVE: W/A/S/D move · Space WAIT · Q FIELD_A · E FIELD_B.
            Requests only; physics realizes.
          </div>
          <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
            {(['MOVE:N', 'MOVE:S', 'MOVE:W', 'MOVE:E', 'WAIT'] as const).map(a => (
              <button key={a} disabled={!active} title={moveWhy} onClick={() => sendCmd('ACTION', a)}>{a}</button>
            ))}
          </div>
        </InspectorAccordion>
      )}

      {show('fields') && (
        <InspectorAccordion id="exp-fields" title="Fields / specimen replay" defaultOpen>
          <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <button disabled={!active} title={moveWhy} onClick={() => sendCmd('FIELD_A')}>FIELD_A</button>
            <button disabled={!active} title={moveWhy} onClick={() => sendCmd('FIELD_B')}>FIELD_B</button>
          </div>
          <div className="metric"><span>SIGNAL LIBRARY</span><strong>NATURAL SPECIMEN REPLAY</strong></div>
          <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <select
              value={selectedSpecimen}
              onChange={e => setSelectedSpecimen(e.target.value)}
              style={{ minWidth: 0, flex: '1 1 160px' }}
            >
              <option value="">— select specimen —</option>
              {specimens.map(s => (
                <option key={String(s.specimen_id)} value={String(s.specimen_id)}>
                  {String(s.specimen_id)} · {String(s.channel || '?')}
                </option>
              ))}
            </select>
            <button disabled={!active || !selectedSpecimen || !!busy} title={moveWhy} onClick={replaySpecimen}>
              REPLAY FROM BODY
            </button>
            <button onClick={refreshSpecimens}>↻</button>
          </div>
          <div className="subtle">No semantic labels. Physical footprint replay only.</div>
        </InspectorAccordion>
      )}

      {show('interaction') && (
        <InspectorAccordion id="exp-interact" title="Interaction" defaultOpen>
          <div className="metric"><span>INTERACTION TARGET</span><strong>Observer-only</strong></div>
          <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <button onClick={() => experimenterSetTarget('agent_0').then(onRefresh)}>agent_0</button>
            <button onClick={() => experimenterSetTarget('agent_1').then(onRefresh)}>agent_1</button>
            <button onClick={() => experimenterSetTarget(null).then(onRefresh)}>clear</button>
          </div>
          {st.target && (
            <div className="subtle">
              {String(st.target.agent_id)} · dist={fmt(st.target.distance)} ·
              action={String(st.target.action)} · src={String(st.target.selection_source)}
            </div>
          )}
          <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <button className="active" disabled={!!busy} onClick={capture}>CAPTURE INTERACTION</button>
            <button disabled={!!busy} onClick={testLast}>TEST THIS INTERACTION</button>
          </div>
          {(st.captures || []).length > 0 && (
            <div className="subtle">
              Captures: {(st.captures || []).map(c => c.capture_id).join(', ')}
            </div>
          )}
          {testResult && (
            <div>
              <div className="metric">
                <span>MATCHED TEST</span>
                <strong>{String((testResult.factorial as any)?.SOURCE_CONTEXT_DEPENDENCE || '—')}</strong>
              </div>
              <pre className="insp-pre">
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
        </InspectorAccordion>
      )}

      {show('camera') && (
        <InspectorAccordion id="exp-camera" title="Camera" defaultOpen>
          <div className="subtle">Observer-only view. Does not change organism physics.</div>
          <div className="toolbar-row" style={{ gap: 8, flexWrap: 'wrap' }}>
            {(['FREE', 'YOU', 'TARGET'] as const).map(c => (
              <button key={c} className={cameraFollow === c ? 'active' : ''} onClick={() => cameraFollowStore.set(c)}>
                {c === 'YOU' ? 'FOLLOW CONTROLLED' : c === 'TARGET' ? 'FOLLOW TARGET' : 'FREE'}
              </button>
            ))}
          </div>
        </InspectorAccordion>
      )}
    </div>
  );
}

function fmt(v: unknown) {
  if (typeof v === 'number' && Number.isFinite(v)) return v.toFixed(2);
  return '—';
}
