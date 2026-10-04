/** SELECTED ORGANISM AUDITORY VIEW (SAV1 visual) + SONIFICATION (SAV2 playback). */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Sav2PlaybackEngine } from './sav2PlaybackEngine.ts';
import {
  PLAYBACK_TIME_SCALE_OPTIONS,
  SAV2_CARRIER_LABEL,
  SAV2_MODE_LABEL,
  SAV2_WARNING,
  sav2ProfileFromWorld,
} from './sav2Profile.ts';
import { registerSav2Engine } from './sav2EngineBridge.ts';
import { getListeningModeOwner, subscribeListeningMode } from './listeningModeOwner.ts';

const MODE = 'SELECTED ORGANISM AUDITORY VIEW';
const WARNING =
  'ORGANISM SENSORY CHANNEL MONITOR · POST-PHENOTYPE · PRE-COGNITION · NOT HUMAN HEARING · NOT MIND READING';

function bars(values: number[], side: string, testPrefix: string): ReactNode {
  return (
    <div data-testid={`${testPrefix}-${side}-bars`} style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height: 48 }}>
      {values.map((v, i) => {
        const h = Math.max(2, Math.min(48, Math.round(Number(v) * 48)));
        return (
          <div key={`${side}-${i}`} style={{ textAlign: 'center' }}>
            <div
              title={`band_${i}=${Number(v).toFixed(4)}`}
              style={{
                width: 14,
                height: h,
                background: Number(v) >= 1 - 1e-9 ? '#c66' : '#6af',
                marginBottom: 2,
              }}
            />
            <div className="subtle" style={{ fontSize: 9 }}>{i}</div>
          </div>
        );
      })}
    </div>
  );
}

export function SelectedOrganismAuditoryViewPanel({
  frame,
  executionMode,
  paused,
  runtimeGeneration,
}: {
  frame: any;
  executionMode?: string;
  paused?: boolean;
  runtimeGeneration?: number | null;
}) {
  const world = frame?.world;
  const sav = world?.selected_organism_auditory_view;
  const profile = useMemo(() => sav2ProfileFromWorld(world), [world?.selected_organism_auditory_sonification, world]);
  const engineRef = useRef<Sav2PlaybackEngine | null>(null);
  const [, bump] = useState(0);
  const refresh = () => bump((n) => n + 1);

  if (!engineRef.current) {
    engineRef.current = new Sav2PlaybackEngine({ profile });
  }
  const engine = engineRef.current;

  useEffect(() => {
    registerSav2Engine(engine);
    return () => { registerSav2Engine(null); };
  }, [engine]);

  useEffect(() => subscribeListeningMode(() => refresh()), []);

  useEffect(() => {
    engine.setProfile(profile);
  }, [engine, profile]);

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

  const latest = sav?.latest_for_selected || null;
  const sectionA = latest?.section_a_organism_accessible || {};
  const sectionB = latest?.section_b_researcher_provenance || {};
  const stamp = sectionB.phenotype_clip_stamp || {};
  const left = Array.isArray(sectionA.left_receptor_channels) ? sectionA.left_receptor_channels : [];
  const right = Array.isArray(sectionA.right_receptor_channels) ? sectionA.right_receptor_channels : [];
  const available = !!latest && latest.availability === 'AVAILABLE';
  const selectedAgent = sav?.selected_agent_id ?? frame?.header?.selected_agent_id ?? null;
  const bodyId = latest?.body_id ?? null;

  useEffect(() => {
    engine.setSelection(selectedAgent ? String(selectedAgent) : null, bodyId ? String(bodyId) : null);
    engine.setAvailability(available ? 'AVAILABLE' : (latest?.availability || 'UNAVAILABLE'));
    engine.setCompatible(available || !!world?.selected_organism_auditory_sonification);
    refresh();
  }, [engine, selectedAgent, bodyId, available, latest?.availability, world?.selected_organism_auditory_sonification]);

  useEffect(() => {
    if (latest && available) {
      engine.feedReceipt(latest, executionMode || 'LIVE');
    }
    refresh();
  }, [engine, latest?.receipt_id, latest?.scientific_tick, selectedAgent, executionMode, available]);

  useEffect(() => () => {
    engine.disable();
  }, [engine]);

  if (!sav && !world?.local_signal_summary && !world?.observer_acoustic_probe) return null;

  const snap = engine.snapshot();
  const carriers = profile.canonical_playback_carrier_hz;
  const mappedL = snap.lastMapped?.left || [];
  const mappedR = snap.lastMapped?.right || [];

  return (
    <div className="panel" data-testid="selected-organism-auditory-view-panel" style={{ marginTop: 8 }}>
      <div data-testid="sav1-mode-label" className="observer-banner researcher-only">{MODE}</div>
      <div data-testid="sav1-warning" className="subtle" style={{ marginTop: 4, fontWeight: 600 }}>
        {WARNING}
      </div>
      <div className="subtle" data-testid="sav1-meta" style={{ marginTop: 4 }}>
        selected={selectedAgent ?? '—'}
        {' · '}body={bodyId ?? '—'}
        {' · '}tick={latest?.scientific_tick ?? '—'}
        {' · '}receipt={latest?.receipt_id ?? '—'}
        {' · '}boundary={sav?.boundary ?? latest?.boundary ?? 'A5'}
        {' · '}profile={sav?.profile ?? '—'}
        {' · '}available={String(available)}
        {' · '}history={sav?.retained_count ?? 0}/{sav?.history_capacity ?? 128}
        {' · '}evicted={sav?.evicted_count ?? 0}
        {' · '}capture={sav?.capture_count ?? 0}
        {' · '}dedup={sav?.deduplicated_count ?? 0}
      </div>

      <div data-testid="sav1-section-a" style={{ marginTop: 8, borderTop: '1px dashed #666', paddingTop: 6 }}>
        <div className="subtle" style={{ fontWeight: 700 }}>A · WHAT THE ORGANISM RECEIVED</div>
        <div className="subtle">organism_accessible=true · post_phenotype · pre_cognition · anonymous bands</div>
        {!available ? (
          <div className="subtle" data-testid="sav1-unavailable">
            {latest?.availability || 'SELECTED_ORGANISM_AUDITORY_VIEW_UNAVAILABLE_LEGACY_EVIDENCE / no receipt yet'}
          </div>
        ) : (
          <>
            <div className="subtle" style={{ marginTop: 4 }}>ORGANISM LEFT RECEPTOR CHANNELS</div>
            {bars(left.map(Number), 'left', 'sav1')}
            <div className="subtle">[{left.map((v: number) => Number(v).toFixed(3)).join(', ')}]</div>
            <div className="subtle" style={{ marginTop: 4 }}>ORGANISM RIGHT RECEPTOR CHANNELS</div>
            {bars(right.map(Number), 'right', 'sav1')}
            <div className="subtle">[{right.map((v: number) => Number(v).toFixed(3)).join(', ')}]</div>
            <div className="subtle" data-testid="sav1-clip-indicators" style={{ marginTop: 4 }}>
              ORGANISM RECEPTOR CLIPPING
              {' · '}clip_range=[{(sectionA.clipping_range || [0, 1]).join(', ')}]
              {' · '}zero_silence={String(!!sectionA.zero_vector_is_legitimate_silence)}
              {' · '}ceiling_L={JSON.stringify(stamp.per_band_at_ceiling_left || [])}
              {' · '}ceiling_R={JSON.stringify(stamp.per_band_at_ceiling_right || [])}
            </div>
          </>
        )}
      </div>

      <div data-testid="sav1-section-b" style={{ marginTop: 8, borderTop: '1px dashed #666', paddingTop: 6 }}>
        <div className="subtle" style={{ fontWeight: 700 }}>B · RESEARCHER CAUSAL PROVENANCE</div>
        <div className="subtle">organism_accessible=false · NOT agent input · NOT cognition · NOT SAV2 amplitude source</div>
        <div className="subtle" data-testid="sav1-phenotype-stamp">
          phenotype={stamp.phenotype_profile ?? '—'}
          {' · '}digest={stamp.phenotype_config_digest ?? '—'}
          {' · '}sensor_scale={stamp.sensor_scale ?? '—'}
          {' · '}heading={stamp.heading_authority ?? '—'}
          {' · '}offset={stamp.receptor_offset ?? '—'}
          {' · '}clipped_count={String(stamp.clipped_count ?? 'NOT_ESTABLISHED')}
          {' · '}obs_key={sectionB.observation_key ?? latest?.observation_key ?? '—'}
        </div>
      </div>

      {/* ——— SAV2 playback section ——— */}
      <div
        data-testid="selected-organism-auditory-sonification-panel"
        style={{ marginTop: 10, borderTop: '2px solid #888', paddingTop: 8 }}
      >
        <div data-testid="sav2-mode-label" className="observer-banner researcher-only">{SAV2_MODE_LABEL}</div>
        <div data-testid="sav2-input-authority" className="subtle" style={{ marginTop: 2, fontWeight: 600 }}>
          RECEPTOR VALUES AVAILABLE TO SELECTED ORGANISM
        </div>
        <div data-testid="sav2-warning" className="subtle" style={{ marginTop: 4, fontWeight: 600 }}>
          {SAV2_WARNING}
        </div>
        <div className="subtle" data-testid="sav2-carriers" style={{ marginTop: 2 }}>
          {SAV2_CARRIER_LABEL}: [{carriers.map((h) => Number(h).toFixed(0)).join(', ')}] (playback only)
        </div>
        <div className="subtle" data-testid="sav2-mode-owner" style={{ marginTop: 2 }}>
          listening_mode_owner={getListeningModeOwner()} · MUTUALLY_EXCLUSIVE with C1 · ORIGINAL=NOT AVAILABLE
        </div>
        <div className="subtle" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 6 }}>
          <button
            type="button"
            data-testid="sav2-enable-listening"
            disabled={snap.listening || !available}
            onClick={async () => {
              await engine.enableListening();
              refresh();
            }}
          >
            Enable Selected-Organism Listening
          </button>
          <button
            type="button"
            data-testid="sav2-disable-listening"
            disabled={!snap.listening && snap.audioState === 'closed'}
            onClick={() => { engine.disable(); refresh(); }}
          >
            Disable
          </button>
          <label>
            Mute{' '}
            <input
              data-testid="sav2-mute"
              type="checkbox"
              checked={snap.muted}
              onChange={(e) => { engine.setMute(e.target.checked); refresh(); }}
            />
          </label>
          <label>
            Monitor Volume{' '}
            <input
              data-testid="sav2-volume"
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
              data-testid="sav2-time-scale"
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
            data-testid="sav2-clear-diagnostics"
            onClick={() => { engine.clearDiagnostics(); refresh(); }}
          >
            Clear SAV2 Playback Diagnostics
          </button>
        </div>
        {!available ? (
          <div className="subtle" data-testid="sav2-unavailable" style={{ marginTop: 4 }}>
            SAV2 unavailable — no valid SAV1 A5 receipt for selected organism
            (no fabricated zero hearing · no probe fallback · no silent agent switch)
          </div>
        ) : null}
        <div className="subtle" data-testid="sav2-meta" style={{ marginTop: 4 }}>
          agent={snap.selectedAgentId ?? '—'}
          {' · '}body={snap.selectedBodyId ?? '—'}
          {' · '}A5={snap.availability}
          {' · '}receipt={snap.diagnostics.last_consumed_key ?? latest?.receipt_id ?? '—'}
          {' · '}tick={snap.diagnostics.last_consumed_tick ?? latest?.scientific_tick ?? '—'}
          {' · '}SAV2={profile.profile}
          {' · '}C0={world?.acoustic_calibration_status?.profile || 'ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1'}
          {' · '}carriers_via={profile.carrier_authority}
          {' · '}AudioContext={snap.audioState}
          {' · '}mode_policy={snap.modeStatus}
          {' · '}authority={profile.authority_class}
        </div>
        <div className="subtle" data-testid="sav2-amplitudes" style={{ marginTop: 2 }}>
          L_act=[{left.map((v: number) => Number(v).toFixed(3)).join(',') || '—'}]
          {' · '}R_act=[{right.map((v: number) => Number(v).toFixed(3)).join(',') || '—'}]
          {' · '}L_amp=[{mappedL.map((v) => Number(v).toFixed(3)).join(',') || '—'}]
          {' · '}R_amp=[{mappedR.map((v) => Number(v).toFixed(3)).join(',') || '—'}]
          {' · '}gain={profile.fixed_receptor_gain}
          {' · '}map={profile.amplitude_mapping}
        </div>
        <div className="subtle" data-testid="sav2-clip-vs-limiter" style={{ marginTop: 2 }}>
          ORGANISM RECEPTOR CLIPPING (A5) ≠ PLAYBACK SAFETY LIMITING (SAV2)
          {' · '}playback_limiter={snap.diagnostics.limiter_activations}
          {' · '}organism_clip_stamp={String(stamp.clipped_count ?? 'NOT_ESTABLISHED')}
        </div>
        <div className="subtle" data-testid="sav2-diagnostics" style={{ marginTop: 2 }}>
          queue={snap.diagnostics.queue_length}/{snap.diagnostics.queue_capacity}
          {' · '}observed={snap.diagnostics.observed}
          {' · '}eligible={snap.diagnostics.eligible}
          {' · '}dedup={snap.diagnostics.deduplicated}
          {' · '}rendered={snap.diagnostics.rendered}
          {' · '}dropped={snap.diagnostics.dropped}
          {' · '}gaps={snap.diagnostics.missing_gap_ticks}
          {' · '}invalid_clamp={snap.diagnostics.invalid_clamped}
          {' · '}L_nz={snap.diagnostics.left_nonzero_bands}
          {' · '}R_nz={snap.diagnostics.right_nonzero_bands}
          {' · '}mute={String(snap.muted)} · vol={snap.volume.toFixed(2)} · scale={snap.playbackTimeScale}×
        </div>
        <div className="subtle" data-testid="sav2-live-status" style={{ marginTop: 4 }}>
          {snap.listening
            ? 'Live SAV2 listening — indefinite monitor; no fabricated percent · stereo L→L R→R translation only'
            : 'SAV2 disabled · Enable requires user gesture · not literal organism sound · not human binaural'}
        </div>
      </div>
    </div>
  );
}
