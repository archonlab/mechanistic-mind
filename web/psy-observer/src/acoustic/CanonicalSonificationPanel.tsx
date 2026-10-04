/** Observer UI — CANONICAL PHYSICAL-FIELD SONIFICATION (C1). */
import { useEffect, useMemo, useRef, useState } from 'react';
import { C1PlaybackEngine } from './c1PlaybackEngine.ts';
import {
  C1_MODE_LABEL,
  C1_WARNING,
  CARRIER_LABEL,
  PLAYBACK_TIME_SCALE_OPTIONS,
  profileFromWorld,
  REQUIRED_C0_PROFILE,
  REQUIRED_PROBE_SCHEMA,
} from './c1Profile.ts';
import { registerC1Engine } from './c1EngineBridge.ts';
import { c0c1Compatible } from './c1Transform.ts';
import { getListeningModeOwner, subscribeListeningMode } from './listeningModeOwner.ts';

export function CanonicalSonificationPanel({
  frame,
  executionMode,
  paused,
  runtimeGeneration,
}: {
  frame: any;
  executionMode: string;
  paused: boolean;
  runtimeGeneration: number | null;
}) {
  const world = frame?.world;
  const probe = world?.observer_acoustic_probe;
  const c1World = world?.canonical_physical_field_sonification;
  const profile = useMemo(() => profileFromWorld(world), [c1World, world]);
  const engineRef = useRef<C1PlaybackEngine | null>(null);
  const [, bump] = useState(0);
  const refresh = () => bump((n) => n + 1);

  if (!engineRef.current) {
    engineRef.current = new C1PlaybackEngine({ profile });
  }
  const engine = engineRef.current;

  useEffect(() => {
    registerC1Engine(engine);
    return () => { registerC1Engine(null); };
  }, [engine]);

  useEffect(() => subscribeListeningMode(() => refresh()), []);

  useEffect(() => {
    engine.setProfile(profile);
  }, [engine, profile]);

  useEffect(() => {
    const c0 = world?.acoustic_calibration_status?.profile
      || world?.acoustic_calibration?.profile
      || REQUIRED_C0_PROFILE;
    const probeSchema = probe?.schema || probe?.latest_sample?.schema || REQUIRED_PROBE_SCHEMA;
    // If probe panel exists under Acanthostega LPS, treat as compatible when C0 present.
    const ok = c0c1Compatible(c0, probeSchema)
      || (c0 === REQUIRED_C0_PROFILE && !!probe);
    engine.setCompatible(ok || !!c1World);
  }, [engine, world, probe, c1World]);

  useEffect(() => {
    const rid = `gen:${runtimeGeneration ?? 'na'}|model:${frame?.header?.model_display_name || 'x'}`;
    engine.setRunId(rid);
  }, [engine, runtimeGeneration, frame?.header?.model_display_name]);

  useEffect(() => {
    engine.setExecutionMode(executionMode || 'LIVE');
    refresh();
  }, [engine, executionMode]);

  useEffect(() => {
    engine.setPaused(!!paused);
    refresh();
  }, [engine, paused]);

  // Feed latest sample on frame updates (deduped inside engine).
  useEffect(() => {
    const latest = probe?.latest_sample;
    if (latest) engine.feedLatest(latest, executionMode || 'LIVE');
    refresh();
  }, [engine, probe?.latest_sample?.sample_key, probe?.latest_sample?.scientific_tick, executionMode]);

  // Probe move / disable
  const probePose = `${probe?.enabled}:${probe?.x}:${probe?.y}`;
  const prevPose = useRef(probePose);
  useEffect(() => {
    if (prevPose.current !== probePose) {
      engine.onProbeMoveOrDisable();
      prevPose.current = probePose;
      refresh();
    }
  }, [engine, probePose]);

  useEffect(() => () => {
    engine.disable();
  }, [engine]);

  const snap = engine.snapshot();
  const carriers = profile.canonical_playback_carrier_hz;
  const bands = Array.isArray(probe?.latest_sample?.anonymous_band_energies)
    ? probe.latest_sample.anonymous_band_energies
    : [];

  if (!probe && !c1World && !world?.local_signal_summary) return null;

  return (
    <div className="panel" data-testid="canonical-physical-field-sonification-panel" style={{ marginTop: 8 }}>
      <div data-testid="c1-mode-label" className="observer-banner researcher-only">
        {C1_MODE_LABEL}
      </div>
      <div data-testid="c1-input-authority" className="subtle" style={{ marginTop: 2, fontWeight: 600 }}>
        PHYSICAL FIELD AT PASSIVE PROBE
      </div>
      <div data-testid="c1-warning" className="subtle" style={{ marginTop: 4, fontWeight: 600 }}>
        {C1_WARNING}
      </div>
      <div className="subtle" data-testid="c1-mode-owner" style={{ marginTop: 2 }}>
        listening_mode_owner={getListeningModeOwner()} · exclusive with SAV2
      </div>
      <div className="subtle" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 6 }}>
        <button
          type="button"
          data-testid="c1-enable-listening"
          disabled={snap.listening}
          onClick={async () => {
            await engine.enableListening();
            refresh();
          }}
        >
          Enable Listening
        </button>
        <button
          type="button"
          data-testid="c1-disable-listening"
          disabled={!snap.listening && snap.audioState === 'closed'}
          onClick={() => { engine.disable(); refresh(); }}
        >
          Disable Listening
        </button>
        <label>
          Mute{' '}
          <input
            data-testid="c1-mute"
            type="checkbox"
            checked={snap.muted}
            onChange={(e) => { engine.setMute(e.target.checked); refresh(); }}
          />
        </label>
        <label>
          Monitor Volume{' '}
          <input
            data-testid="c1-volume"
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={snap.volume}
            onChange={(e) => { engine.setVolume(Number(e.target.value)); refresh(); }}
          />
          <span>{snap.volume.toFixed(2)}</span>
        </label>
        <label>
          Playback Time Scale{' '}
          <select
            data-testid="c1-time-scale"
            value={String(snap.playbackTimeScale)}
            onChange={(e) => { engine.setPlaybackTimeScale(Number(e.target.value)); refresh(); }}
          >
            {PLAYBACK_TIME_SCALE_OPTIONS.map((s) => (
              <option key={s} value={String(s)}>{s}×</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          data-testid="c1-clear-diagnostics"
          onClick={() => { engine.clearDiagnostics(); refresh(); }}
        >
          Clear Playback Diagnostics
        </button>
      </div>
      <div className="subtle" data-testid="c1-meta" style={{ marginTop: 4 }}>
        C0={world?.acoustic_calibration_status?.profile || world?.acoustic_calibration?.profile || '—'}
        {' · '}C1={profile.profile}
        {' · '}probe={probe?.probe_id ?? '—'}
        {' · '}xy=({probe?.x != null ? Number(probe.x).toFixed(3) : '—'},{probe?.y != null ? Number(probe.y).toFixed(3) : '—'})
        {' · '}AudioContext={snap.audioState}
        {' · '}mode_policy={snap.modeStatus}
        {' · '}sr={snap.sampleRate || '—'}
        {' · '}ORIGINAL=NOT AVAILABLE
      </div>
      <div className="subtle" data-testid="c1-carriers" style={{ marginTop: 2 }}>
        {CARRIER_LABEL}: [{carriers.map((h) => Number(h).toFixed(0)).join(', ')}] Hz (playback only)
      </div>
      <div className="subtle" data-testid="c1-bands" style={{ marginTop: 2 }}>
        anonymous bands=[{bands.map((b: number) => Number(b).toFixed(3)).join(',') || '—'}]
      </div>
      <div className="subtle" data-testid="c1-diagnostics" style={{ marginTop: 2 }}>
        queue={snap.diagnostics.queue_length}/{snap.diagnostics.queue_capacity}
        {' · '}horizon={snap.scheduledHorizon}s
        {' · '}observed={snap.diagnostics.observed}
        {' · '}dedup={snap.diagnostics.deduplicated}
        {' · '}rendered={snap.diagnostics.rendered}
        {' · '}dropped={snap.diagnostics.dropped}
        {' · '}underrun={snap.diagnostics.underruns}
        {' · '}limiter={snap.diagnostics.limiter_activations}
        {' · '}last={snap.diagnostics.last_consumed_key ?? '—'}
        {' · '}tick={snap.diagnostics.last_consumed_tick ?? '—'}
        {' · '}mute={String(snap.muted)} · vol={snap.volume.toFixed(2)} · scale={snap.playbackTimeScale}×
      </div>
      <div className="subtle" data-testid="c1-live-status" style={{ marginTop: 4 }}>
        {snap.listening
          ? 'Live listening active — progress percent not fabricated for indefinite monitor'
          : 'Listening disabled · Enable Listening requires explicit user gesture (autoplay policy)'}
      </div>
    </div>
  );
}

/** Notify engine of restore from outside (App lifecycle). */
export function c1NotifyRestore(engine: C1PlaybackEngine | null) {
  engine?.onRestore();
}
