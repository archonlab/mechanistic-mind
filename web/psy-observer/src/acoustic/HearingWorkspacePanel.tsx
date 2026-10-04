/**
 * OBSERVER_LEFT_HEARING_WORKSPACE_V1 — consolidated left-panel hearing UI.
 * Engines live inside reused C1/SAV panels; host must keep this mounted (CSS-hidden OK).
 * Beta4 release repair: compact primary = researcher playback only (World / Agent / Volume).
 */
import { useEffect, useMemo, useState } from 'react';
import { CanonicalSonificationPanel } from './CanonicalSonificationPanel.tsx';
import { SelectedOrganismAuditoryViewPanel } from './SelectedOrganismAuditoryViewPanel.tsx';
import { SelectedOrganismPhysicalFieldComparisonPanel } from './SelectedOrganismPhysicalFieldComparisonPanel.tsx';
import { SelectedOrganismAuditoryOfflineReconstructionPanel } from './SelectedOrganismAuditoryOfflineReconstructionPanel.tsx';
import { PassiveAcousticProbeControls } from './PassiveAcousticProbeControls.tsx';
import {
  getListeningModeOwner,
  releaseListeningMode,
  subscribeListeningMode,
  type ListeningModeOwner,
} from './listeningModeOwner.ts';
import { getRegisteredC1Engine } from './c1EngineBridge.ts';
import { getRegisteredSav2Engine } from './sav2EngineBridge.ts';
import { getRegisteredSav4bEngine } from './sav4bEngineBridge.ts';
import { PhenomenonDetails, type PhenomenonCategory } from '../components/PhenomenonDetails';
import { inspectorUiStore, workspaceStore } from '../observer/stores';
import { classifyHearingPlayback, type HearingPlaybackClassification } from './hearingPlaybackStatus.ts';

const WORKSPACE = 'OBSERVER_LEFT_HEARING_WORKSPACE_V1';
const VOLUME_PREF_KEY = 'mm-observer.hearing.masterVolume';

function loadVolumePref(): number {
  try {
    const raw = localStorage.getItem(VOLUME_PREF_KEY);
    if (raw == null) return 0.7;
    const n = Number(raw);
    if (!Number.isFinite(n)) return 0.7;
    return Math.max(0, Math.min(1, n));
  } catch {
    return 0.7;
  }
}

function saveVolumePref(v: number) {
  try {
    localStorage.setItem(VOLUME_PREF_KEY, String(v));
  } catch {
    /* ignore */
  }
}

function ownerLabel(o: ListeningModeOwner): string {
  if (o === 'PHYSICAL_FIELD_C1') return 'PHYSICAL FIELD C1';
  if (o === 'SELECTED_ORGANISM_SAV2') return 'SELECTED ORGANISM SAV2';
  if (o === 'OFFLINE_SAV4B') return 'OFFLINE SAV4B';
  return 'OFF';
}

function StatusBlock({ cls, testId }: { cls: HearingPlaybackClassification; testId: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(cls.signalLevel * 100)));
  return (
    <div className="subtle" role="status" data-testid={testId}>
      <div data-testid={`${testId}-label`} style={{ fontWeight: 600 }}>{cls.status}</div>
      <div data-testid={`${testId}-source`}>source={cls.sourceMode}</div>
      <div data-testid={`${testId}-tick`}>auditory tick={cls.latestTick ?? '—'}</div>
      <div data-testid={`${testId}-level`} aria-label="signal level">
        level
        <span style={{ display: 'inline-block', width: 64, height: 6, margin: '0 6px', background: '#333', verticalAlign: 'middle' }}>
          <span style={{ display: 'block', width: `${pct}%`, height: 6, background: pct > 0 ? '#8c8' : '#666' }} />
        </span>
        {pct}%
      </div>
      <div data-testid={`${testId}-volume`}>master={Math.round(cls.masterVolume * 100)}%</div>
      <div data-testid={`${testId}-audio-context`}>AudioContext={cls.audioContextState}</div>
      <details data-testid={`${testId}-info`}>
        <summary>ⓘ</summary>
        <div>{cls.explanation}</div>
      </details>
    </div>
  );
}

export function HearingWorkspacePanel({
  frame,
  executionMode,
  paused,
  runtimeGeneration,
  selectedCell,
  compact,
  dockVisible = true,
  onOpenDetailed,
}: {
  frame: any;
  executionMode: string;
  paused: boolean;
  runtimeGeneration: number | null;
  selectedCell?: any;
  /** When true, settings-first compact hierarchy (S7D Eye Hearing). */
  compact?: boolean;
  /** When false, suspend researcher playback (Eye dock closed / not Hearing). */
  dockVisible?: boolean;
  onOpenDetailed?: () => void;
}) {
  const [, bump] = useState(0);
  const [masterVolume, setMasterVolume] = useState(loadVolumePref);
  const [listenAgentId, setListenAgentId] = useState<string | null>(null);
  const [exclusiveNote, setExclusiveNote] = useState<string | null>(null);

  useEffect(() => subscribeListeningMode(() => bump((n) => n + 1)), []);

  const owner = getListeningModeOwner();
  const c1 = getRegisteredC1Engine();
  const sav2 = getRegisteredSav2Engine();
  const c1Snap = c1?.snapshot();
  const sav2Snap = sav2?.snapshot();
  const audioState =
    owner === 'PHYSICAL_FIELD_C1'
      ? c1Snap?.audioState
      : owner === 'SELECTED_ORGANISM_SAV2'
        ? sav2Snap?.audioState
        : owner === 'OFFLINE_SAV4B'
          ? (getRegisteredSav4bEngine()?.snapshot().audio_state ?? 'closed')
          : 'closed';
  const profile =
    owner === 'PHYSICAL_FIELD_C1'
      ? c1Snap?.diagnostics
        ? 'C1'
        : '—'
      : owner === 'SELECTED_ORGANISM_SAV2'
        ? 'SAV2'
        : owner === 'OFFLINE_SAV4B'
          ? 'SAV4B'
          : '—';

  const world = frame?.world;
  const stream = world?.authoritative_physical_acoustic_stream;
  const cal = world?.acoustic_calibration_status || world?.acoustic_calibration;
  const sav = world?.selected_organism_auditory_view;
  const globalSelectedAgent = sav?.selected_agent_id ?? frame?.header?.selected_agent_id ?? null;
  const agentIds: string[] = useMemo(() => {
    const fromSav = Array.isArray(sav?.available_agent_ids) ? sav.available_agent_ids.map(String) : [];
    const fromRuntime = Array.isArray(frame?.experiment?.runtime?.observer_agent_ids)
      ? frame.experiment.runtime.observer_agent_ids.map(String)
      : [];
    const fromAgents = Array.isArray(frame?.agents_observer)
      ? frame.agents_observer.map((a: any) => String(a?.agent_id || a?.id || '')).filter(Boolean)
      : [];
    const merged = [...new Set([...fromSav, ...fromRuntime, ...fromAgents, ...(globalSelectedAgent ? [String(globalSelectedAgent)] : [])])];
    return merged.length ? merged : ['agent_0'];
  }, [sav?.available_agent_ids, frame?.experiment?.runtime?.observer_agent_ids, frame?.agents_observer, globalSelectedAgent]);

  useEffect(() => {
    if (!listenAgentId || !agentIds.includes(listenAgentId)) {
      setListenAgentId(String(globalSelectedAgent || agentIds[0] || 'agent_0'));
    }
  }, [agentIds, globalSelectedAgent, listenAgentId]);

  const listenReceipt = useMemo(() => {
    const by = sav?.latest_by_agent || {};
    if (listenAgentId && by[listenAgentId]) return by[listenAgentId];
    if (listenAgentId && String(globalSelectedAgent) === String(listenAgentId)) return sav?.latest_for_selected;
    return null;
  }, [sav, listenAgentId, globalSelectedAgent]);

  const savLatest = listenReceipt || sav?.latest_for_selected;
  const sav4b = getRegisteredSav4bEngine();

  // Shared master volume → both engines (playback gain only).
  useEffect(() => {
    c1?.setVolume(masterVolume);
    sav2?.setVolume(masterVolume);
    if (masterVolume <= 0) {
      c1?.setMute(true);
      sav2?.setMute(true);
    } else {
      c1?.setMute(false);
      sav2?.setMute(false);
    }
    bump((n) => n + 1);
  }, [masterVolume, c1, sav2]);

  // Suspend researcher playback when Eye Hearing surface is hidden; keep engines mounted.
  useEffect(() => {
    if (dockVisible) return;
    c1?.disable();
    sav2?.disable();
    if (owner === 'PHYSICAL_FIELD_C1') releaseListeningMode('PHYSICAL_FIELD_C1');
    if (owner === 'SELECTED_ORGANISM_SAV2') releaseListeningMode('SELECTED_ORGANISM_SAV2');
  }, [dockVisible, c1, sav2, owner]);

  // Feed listen-agent into SAV2 without mutating global selection.
  useEffect(() => {
    if (!sav2 || !listenAgentId) return;
    const bodyId = listenReceipt?.body_id ?? null;
    sav2.setSelection(String(listenAgentId), bodyId ? String(bodyId) : null);
    const avail = listenReceipt?.availability || (listenReceipt ? 'AVAILABLE' : 'UNAVAILABLE');
    sav2.setAvailability(avail === 'AVAILABLE' ? 'AVAILABLE' : String(avail || 'UNAVAILABLE'));
    if (listenReceipt && avail === 'AVAILABLE') {
      sav2.feedReceipt(listenReceipt, executionMode || 'LIVE');
    }
    bump((n) => n + 1);
  }, [sav2, listenAgentId, listenReceipt, executionMode, sav?.retained_count]);

  const worldLive = owner === 'PHYSICAL_FIELD_C1' && !!c1Snap?.listening;
  const agentLive = owner === 'SELECTED_ORGANISM_SAV2' && !!sav2Snap?.listening;

  const worldEnergies = Array.isArray(stream?.anonymous_band_energies)
    ? stream.anonymous_band_energies
    : (Array.isArray(c1Snap?.lastProvenance?.mapped_amplitudes)
      ? (c1Snap?.lastProvenance as any).mapped_amplitudes
      : []);
  const worldCls = classifyHearingPlayback({
    listening: worldLive,
    audioContextState: worldLive ? (c1Snap?.audioState || audioState) : (c1Snap?.audioState || 'closed'),
    sourceAvailable: Boolean(stream),
    trueZero: Boolean(stream) && worldEnergies.length > 0 && worldEnergies.every((v: number) => Number(v) === 0),
    energyBands: worldEnergies,
    sourceMode: 'World',
    latestTick: stream?.scientific_tick ?? stream?.tick ?? frame?.header?.tick ?? null,
    masterVolume,
  });
  const agentChannels = listenReceipt?.section_a_organism_accessible?.left_receptor_channels;
  const agentMapped = sav2Snap?.lastMapped
    ? [...(sav2Snap.lastMapped.left || []), ...(sav2Snap.lastMapped.right || [])]
    : (Array.isArray(agentChannels) ? agentChannels : []);
  const agentAvail = listenReceipt?.availability === 'AVAILABLE';
  const agentCls = classifyHearingPlayback({
    listening: agentLive,
    audioContextState: agentLive ? (sav2Snap?.audioState || audioState) : (sav2Snap?.audioState || 'closed'),
    sourceAvailable: agentAvail,
    trueZero: Boolean(listenReceipt?.true_zero) || (agentAvail && Array.isArray(agentChannels) && agentChannels.every((v: number) => Number(v) === 0)),
    mappedAmplitudes: agentMapped,
    sourceMode: String(listenAgentId || 'agent_0'),
    latestTick: listenReceipt?.scientific_tick ?? listenReceipt?.tick ?? listenReceipt?.observation_tick ?? null,
    masterVolume,
  });

  async function startWorld() {
    setExclusiveNote(null);
    if (owner === 'SELECTED_ORGANISM_SAV2') {
      sav2?.disable();
      releaseListeningMode('SELECTED_ORGANISM_SAV2');
      setExclusiveNote('World and Agent playback are mutually exclusive in this build — Agent stopped.');
    }
    if (owner === 'OFFLINE_SAV4B') {
      sav4b?.stop();
      releaseListeningMode('OFFLINE_SAV4B');
    }
    await c1?.enableListening();
    bump((n) => n + 1);
  }

  function stopWorld() {
    c1?.disable();
    releaseListeningMode('PHYSICAL_FIELD_C1');
    bump((n) => n + 1);
  }

  async function startAgent() {
    setExclusiveNote(null);
    if (owner === 'PHYSICAL_FIELD_C1') {
      c1?.disable();
      releaseListeningMode('PHYSICAL_FIELD_C1');
      setExclusiveNote('World and Agent playback are mutually exclusive in this build — World stopped.');
    }
    if (owner === 'OFFLINE_SAV4B') {
      sav4b?.stop();
      releaseListeningMode('OFFLINE_SAV4B');
    }
    if (!listenReceipt || listenReceipt.availability === 'UNAVAILABLE') {
      bump((n) => n + 1);
      return;
    }
    await sav2?.enableListening();
    bump((n) => n + 1);
  }

  function stopAgent() {
    sav2?.disable();
    releaseListeningMode('SELECTED_ORGANISM_SAV2');
    bump((n) => n + 1);
  }

  function onListenAgentChange(next: string) {
    setListenAgentId(next);
    // Do NOT mutate global selected simulation agent.
    if (agentLive && sav2) {
      const by = sav?.latest_by_agent || {};
      const rec = by[next] || (String(globalSelectedAgent) === next ? sav?.latest_for_selected : null);
      const bodyId = rec?.body_id ?? null;
      sav2.setSelection(next, bodyId ? String(bodyId) : null);
      if (rec && rec.availability === 'AVAILABLE') {
        sav2.feedReceipt(rec, executionMode || 'LIVE');
      }
    }
    bump((n) => n + 1);
  }

  function onVolumeChange(v: number) {
    const clamped = Math.max(0, Math.min(1, v));
    setMasterVolume(clamped);
    saveVolumePref(clamped);
  }

  const categories: PhenomenonCategory[] = useMemo(() => [
    {
      id: 'signal',
      title: 'Signal availability',
      summary: savLatest?.availability === 'AVAILABLE' ? 'AVAILABLE' : String(savLatest?.availability || 'UNAVAILABLE'),
      children: (
        <div className="subtle">
          <div>TRUE ZERO ≠ UNAVAILABLE. Researcher playback ≠ organism hearing.</div>
          <div>availability={String(savLatest?.availability || '—')}{savLatest?.true_zero ? ' · TRUE ZERO' : ''}</div>
        </div>
      ),
    },
    {
      id: 'authority',
      title: 'Physical field / receptor / cognition distinction',
      summary: 'four authorities',
      children: (
        <div className="subtle">
          <div>physical acoustic field ≠ receptor acceptance ≠ cognition ≠ researcher playback</div>
        </div>
      ),
    },
    {
      id: 'lps',
      title: 'LPS / OATT timing',
      summary: 'transport ≠ alignment',
      children: <div className="subtle">LPS delay is physical transport — distinct from OATT A3→A5 alignment.</div>,
    },
    {
      id: 'provenance',
      title: 'Authority and provenance',
      summary: `owner=${ownerLabel(owner)}`,
      children: (
        <div className="subtle">
          <div>C0={cal?.profile ?? '—'} · stage={cal?.authority_stage ?? '—'}</div>
          <div>Hz/SPL = NOT ESTABLISHED · ORIGINAL = NOT AVAILABLE</div>
          <div>workspace={WORKSPACE}</div>
        </div>
      ),
    },
    {
      id: 'limits',
      title: 'Limitations',
      summary: 'exclusive playback · no new samples from Live',
      children: (
        <div className="subtle">
          World and Agent playback are mutually exclusive. Live does not create scientific samples.
          Stop ends researcher playback only — organism hearing / capture continue.
        </div>
      ),
    },
  ], [savLatest, owner, cal]);

  const compactPrimary = (
    <div className="panel hearing-primary-controls" data-testid="hearing-primary-controls" style={{ marginTop: 8 }}>
      <div className="subtle" style={{ fontWeight: 700 }} data-testid="hearing-workspace-title">HEARING</div>

      <div style={{ marginTop: 8 }} data-testid="hearing-listen-world">
        <div className="subtle" style={{ fontWeight: 600 }}>Listen World</div>
        <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
          <button type="button" data-testid="hearing-world-live" className={worldLive ? 'active' : ''} onClick={() => { void startWorld(); }}>
            Live
          </button>
          <button type="button" data-testid="hearing-world-stop" onClick={stopWorld}>Stop</button>
        </div>
        <div className="subtle" role="status" data-testid="hearing-world-playback-state">
          <StatusBlock cls={worldCls} testId="hearing-world-status" />
        </div>
      </div>

      <div style={{ marginTop: 10 }} data-testid="hearing-listen-agent">
        <div className="subtle" style={{ fontWeight: 600 }}>Listen Agent</div>
        <label className="subtle" style={{ display: 'block', marginTop: 4 }}>
          <span className="sr-only">Listen agent</span>
          <select
            data-testid="hearing-listen-agent-select"
            value={listenAgentId || ''}
            onChange={(e) => onListenAgentChange(e.target.value)}
            aria-label="Listen agent (does not change globally selected simulation agent)"
          >
            {agentIds.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </label>
        <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
          <button
            type="button"
            data-testid="hearing-agent-live"
            className={agentLive ? 'active' : ''}
            disabled={!listenReceipt || listenReceipt.availability === 'UNAVAILABLE'}
            onClick={() => { void startAgent(); }}
          >
            Live
          </button>
          <button type="button" data-testid="hearing-agent-stop" onClick={stopAgent}>Stop</button>
        </div>
        <div className="subtle" role="status" data-testid="hearing-agent-playback-state">
          <StatusBlock cls={agentCls} testId="hearing-agent-status" />
        </div>
        <div className="subtle">Listen selection does not change the globally selected simulation agent.</div>
      </div>

      <div style={{ marginTop: 10 }} data-testid="hearing-master-volume">
        <div className="subtle" style={{ fontWeight: 600 }}>Volume</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round(masterVolume * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(masterVolume * 100)}
            aria-label="Master researcher playback volume"
            data-testid="hearing-master-volume-slider"
            onChange={(e) => onVolumeChange(Number(e.target.value) / 100)}
            style={{ flex: 1 }}
          />
          <strong data-testid="hearing-master-volume-pct">{Math.round(masterVolume * 100)}%</strong>
        </label>
        <div className="subtle">Playback gain only — not simulation amplitude.</div>
      </div>

      {exclusiveNote ? (
        <div className="subtle" role="status" data-testid="hearing-exclusive-note" style={{ marginTop: 6 }}>
          {exclusiveNote}
        </div>
      ) : (
        <div className="subtle" data-testid="hearing-exclusive-policy" style={{ marginTop: 6 }}>
          Simultaneous World+Agent playback is not supported — one audible owner at a time.
        </div>
      )}

      <button
        type="button"
        data-testid="hearing-open-detailed"
        style={{ marginTop: 8 }}
        onClick={() => {
          if (onOpenDetailed) {
            onOpenDetailed();
            return;
          }
          const ui = inspectorUiStore.get();
          inspectorUiStore.set({
            ...ui,
            leftSensoryMode: 'HEARING',
            eyeDockMode: 'CLOSED',
          });
          const cur = workspaceStore.get();
          workspaceStore.set({ ...cur, workspace: 'INSPECT' });
        }}
      >
        Open detailed Hearing
      </button>
    </div>
  );

  return (
    <div
      className={`hearing-workspace ${compact ? 'compact' : ''}`}
      data-testid="observer-left-hearing-workspace"
      data-workspace={WORKSPACE}
      data-capability="observer_left_hearing_workspace"
      data-compact={String(Boolean(compact))}
    >
      {compact ? compactPrimary : (
        <>
          <div className="subtle" style={{ fontWeight: 700 }} data-testid="hearing-workspace-title">
            HEARING · RESEARCHER SENSORY WORKSPACE
          </div>
          <div className="subtle" data-testid="hearing-selected-agent">
            selected agent={String(globalSelectedAgent || '—').toUpperCase()} · same authority as VISION
          </div>
        </>
      )}

      {!compact ? (
        <div className="panel hearing-section" data-testid="hearing-listening-mode" style={{ marginTop: 8 }}>
          <div className="subtle" style={{ fontWeight: 700 }}>LISTENING MODE (detailed)</div>
          <div className="subtle" data-testid="hearing-mode-owner">
            owner={ownerLabel(owner)} · AudioContext={audioState ?? 'closed'} · profile={profile}
          </div>
        </div>
      ) : null}

      {/* Engine hosts — keep mounted for keep-alive; compact hides chrome via CSS */}
      <div data-testid="hearing-physical-field-section" className={compact ? 'hearing-engine-deferred' : undefined}>
        <PassiveAcousticProbeControls frame={frame} selectedCell={selectedCell} />
        <CanonicalSonificationPanel
          frame={frame}
          executionMode={executionMode}
          paused={paused}
          runtimeGeneration={runtimeGeneration}
        />
      </div>

      <div data-testid="hearing-selected-organism-section" className={compact ? 'hearing-engine-deferred' : undefined}>
        <SelectedOrganismAuditoryViewPanel
          frame={frame}
          executionMode={executionMode}
          paused={paused}
          runtimeGeneration={runtimeGeneration}
        />
      </div>

      {compact ? (
        <PhenomenonDetails categories={categories} testIdPrefix="hearing-dock" />
      ) : (
        <div className="panel hearing-section" data-testid="hearing-acoustic-status" style={{ marginTop: 8 }}>
          <div className="subtle" style={{ fontWeight: 700 }}>ACOUSTIC STATUS</div>
          <div className="subtle" style={{ marginTop: 6 }}>
            <div data-testid="hearing-stream-counts">
              stream retained={stream?.retained_count ?? '—'} · seq={stream?.next_sequence != null ? Number(stream.next_sequence) - 1 : '—'}
            </div>
            <div data-testid="hearing-c0-status">
              C0={cal?.profile ?? '—'} · stage={cal?.authority_stage ?? '—'}
            </div>
          </div>
          <SelectedOrganismPhysicalFieldComparisonPanel frame={frame} />
          <SelectedOrganismAuditoryOfflineReconstructionPanel frame={frame} />
        </div>
      )}
    </div>
  );
}
