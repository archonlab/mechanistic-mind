/**
 * SAV4A read-only reconstruction + SAV4B offline player controls.
 * SAV4B consumes SAV4A schedule only — no raw evidence re-parse.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  SAV4A_SCHEMA,
  SAV4A_TITLE,
  SAV4A_WARNING_GAPS,
  SAV4A_WARNING_TICK,
  authorityBadge,
} from './sav4aOffline.ts';
import {
  SAV4B_SCHEMA,
  SAV4B_TITLE,
  SAV4B_WARNING,
  SAV4B_WARNING_GAPS,
  SAV4B_WARNING_TICK,
  playbackEnabledForSegment,
  scheduleItemsForSegment,
  segmentDurationSeconds,
} from './sav4bOffline.ts';
import { Sav4bPlaybackEngine } from './sav4bPlaybackEngine.ts';
import { registerSav4bEngine } from './sav4bEngineBridge.ts';
import {
  getListeningModeOwner,
  subscribeListeningMode,
} from './listeningModeOwner.ts';

export {
  SAV4A_SCHEMA,
  SAV4A_TITLE,
  SAV4A_WARNING_GAPS,
  SAV4A_WARNING_TICK,
} from './sav4aOffline.ts';

export function SelectedOrganismAuditoryOfflineReconstructionPanel({
  frame,
  analysis,
}: {
  frame?: any;
  analysis?: any;
}) {
  const [open, setOpen] = useState(false);
  const [segIdx, setSegIdx] = useState(0);
  const [, bump] = useState(0);
  const engineRef = useRef<Sav4bPlaybackEngine | null>(null);
  if (!engineRef.current) {
    engineRef.current = new Sav4bPlaybackEngine({ fake: typeof window === 'undefined' });
  }
  const engine = engineRef.current;

  useEffect(() => {
    registerSav4bEngine(engine);
    const unsub = subscribeListeningMode(() => bump((n) => n + 1));
    return () => {
      unsub();
      engine.stop();
      registerSav4bEngine(null);
    };
  }, [engine]);

  const sav4a = useMemo(() => {
    const fromAnalysis =
      analysis?.selected_organism_auditory_offline_reconstruction
      || analysis?.evidence_extras?.selected_organism_auditory_offline_reconstruction;
    if (fromAnalysis) return fromAnalysis;
    return frame?.world?.selected_organism_auditory_offline_reconstruction || null;
  }, [frame, analysis]);

  const segments: any[] = Array.isArray(sav4a?.identity_segments) ? sav4a.identity_segments : [];
  const safeIdx = segments.length ? Math.min(segIdx, segments.length - 1) : 0;
  const seg = segments[safeIdx] || null;
  const preview: any[] = Array.isArray(sav4a?.normalized_records_preview)
    ? sav4a.normalized_records_preview
    : Array.isArray(sav4a?.normalized_records)
      ? sav4a.normalized_records
      : [];
  const filteredPreview = seg
    ? preview.filter((r) => String(r?.segment_id || '') === String(seg.segment_id))
    : preview;
  const auth = authorityBadge(
    seg?.authority_badge
      || (sav4a?.authority_matrix
        && Object.keys(sav4a.authority_matrix).find((k) => (sav4a.authority_matrix[k] || 0) > 0)),
  );
  const legacyDowngrade = auth === 'LEGACY A5' || Boolean(seg?.authority_badge === 'LEGACY_OSC_A5_ONLY');
  const playGate = playbackEnabledForSegment(sav4a, seg);
  const items = seg && sav4a ? scheduleItemsForSegment(sav4a, String(seg.segment_id || '')) : [];
  const duration = segmentDurationSeconds(items);
  const multiSeg = segments.length > 1;

  useEffect(() => {
    if (!seg || !sav4a) {
      engine.clearSchedule();
      bump((n) => n + 1);
      return;
    }
    engine.setSchedule(items, {
      segmentId: String(seg.segment_id || ''),
      scheduleDigest: String(sav4a.schedule_digest || ''),
      treatEndAsGapBoundary: multiSeg,
    });
    bump((n) => n + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engine, String(seg?.segment_id || ''), String(sav4a?.schedule_digest || ''), items.length, multiSeg]);

  const visible = Boolean(sav4a || frame?.world?.selected_organism_auditory_view);
  const snap = engine.snapshot();
  const owner = getListeningModeOwner();

  async function onPlay() {
    if (!playGate.enabled) return;
    await engine.play();
    bump((n) => n + 1);
  }
  function onPause() {
    engine.pause();
    bump((n) => n + 1);
  }
  function onStop() {
    engine.stop();
    bump((n) => n + 1);
  }
  function onSeekTick(raw: string) {
    const t = Number(raw);
    if (!Number.isFinite(t)) return;
    engine.seekTick(t);
    bump((n) => n + 1);
  }

  if (!visible) return null;

  return (
    <div className="panel hearing-section" data-testid="hearing-sav4a-section" style={{ marginTop: 8 }}>
      <button
        type="button"
        data-testid="hearing-sav4a-toggle"
        onClick={() => setOpen((v) => !v)}
        style={{ border: 0, background: 'transparent', padding: 0, cursor: 'pointer', fontWeight: 700 }}
      >
        {SAV4A_TITLE} {open ? '▾' : '▸'}
      </button>
      {open ? (
        <div style={{ marginTop: 6 }} data-testid="hearing-sav4a-body">
          <div className="subtle" data-testid="hearing-sav4a-schema">{SAV4A_SCHEMA}</div>
          <div className="subtle" data-testid="hearing-sav4a-evidence-id">
            evidence run_id={String(sav4a?.run_id ?? '—')} · gen={String(sav4a?.default_runtime_generation ?? seg?.runtime_generation ?? '—')}
            {' · '}scope={String(sav4a?.evidence_scope ?? 'SAVED_OR_LIVE_TIP')}
          </div>
          <div className="subtle" data-testid="hearing-live-vs-saved">
            mode contrast: LIVE C1/SAV2 ≠ SAVED-RUN OFFLINE SAV4B
          </div>
          {segments.length > 1 ? (
            <label className="subtle" style={{ display: 'block', marginTop: 4 }} data-testid="hearing-sav4a-identity-selector">
              identity segment{' '}
              <select
                value={safeIdx}
                onChange={(e) => setSegIdx(Number(e.target.value))}
                data-testid="hearing-sav4a-segment-select"
              >
                {segments.map((s, i) => (
                  <option key={String(s.segment_id || i)} value={i}>
                    {`${s.agent_id}/${s.body_id} gen=${s.runtime_generation} [${s.first_tick}..${s.last_tick}]`}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div style={{ marginTop: 6 }} data-testid="hearing-sav4a-badges">
            <span data-testid="hearing-sav4a-authority-badge" style={{ fontWeight: 700, marginRight: 8 }}>
              authority: {auth}
            </span>
            <span data-testid="hearing-sav4a-completeness-badge" style={{ marginRight: 8 }}>
              completeness: {String(seg?.completeness ?? sav4a?.status ?? '—')}
            </span>
            {legacyDowngrade ? (
              <span data-testid="hearing-sav4a-legacy-downgrade" style={{ color: '#a60' }}>
                LEGACY A5 — never upgraded to OATT/SAV1
              </span>
            ) : null}
          </div>
          <div className="subtle" data-testid="hearing-sav4a-ticks">
            ticks {String(seg?.first_tick ?? '—')}..{String(seg?.last_tick ?? '—')} · observed={String(seg?.observed_tick_count ?? sav4a?.normalized_record_count ?? '—')}
            {' · '}expected_span={String(seg?.expected_tick_span ?? '—')} · gaps={String(seg?.gap_count ?? sav4a?.gap_count ?? 0)}
          </div>
          <div className="subtle" data-testid="hearing-sav4a-dup-conflict">
            duplicates={String(sav4a?.duplicate_count ?? 0)} · conflicts={String(sav4a?.conflict_count ?? 0)}
          </div>
          <div className="subtle" data-testid="hearing-sav4a-compat">
            profile compatibility={String(seg?.compatibility_class ?? sav4a?.profile_compatibility?.legacy_schedule_policy ?? '—')}
          </div>
          <div className="subtle" data-testid="hearing-sav4a-schedule">
            schedule={sav4a?.schedule_available || seg?.schedule_available ? 'AVAILABLE' : 'UNAVAILABLE'}
            {' · '}items={String(items.length || sav4a?.schedule_item_count || 0)}
            {' · '}digest={String(sav4a?.schedule_digest ?? '—').slice(0, 16)}…
          </div>
          <div className="subtle" style={{ marginTop: 6 }} data-testid="hearing-sav4a-warnings">
            <div>{SAV4A_WARNING_GAPS}</div>
            <div>{SAV4A_WARNING_TICK}</div>
          </div>
          <div style={{ marginTop: 6 }} data-testid="hearing-sav4a-timeline-preview">
            <div className="subtle" style={{ fontWeight: 700 }}>bounded timeline preview</div>
            {(filteredPreview.length ? filteredPreview : preview).slice(0, 12).map((r) => (
              <div key={String(r.record_id)} className="subtle" data-testid="hearing-sav4a-preview-row">
                t={r.observation_tick} · {authorityBadge(r.source_authority_class)}
                {' · '}true_zero={String(Boolean(r.true_zero))}
                {' · '}conflict={String(r.conflict_status || 'NONE')}
              </div>
            ))}
            {!preview.length ? <div className="subtle">No normalized records in preview</div> : null}
          </div>

          {/* SAV4B offline player */}
          <div style={{ marginTop: 10 }} data-testid="hearing-sav4b-section">
            <div style={{ fontWeight: 700 }} data-testid="hearing-sav4b-title">{SAV4B_TITLE}</div>
            <div className="subtle" data-testid="hearing-sav4b-schema">{SAV4B_SCHEMA}</div>
            <div className="subtle" data-testid="hearing-sav4b-warning">{SAV4B_WARNING}</div>
            <div className="subtle">{SAV4B_WARNING_GAPS}</div>
            <div className="subtle">{SAV4B_WARNING_TICK}</div>
            <div className="subtle" data-testid="hearing-sav4b-identity">
              run={String(seg?.run_id ?? sav4a?.run_id ?? '—')}
              {' · '}gen={String(seg?.runtime_generation ?? '—')}
              {' · '}agent={String(seg?.agent_id ?? '—')}
              {' · '}body={String(seg?.body_id ?? '—')}
              {' · '}segment={String(seg?.segment_id ?? '—').slice(0, 12)}
            </div>
            <div className="subtle" data-testid="hearing-sav4b-status">
              playback={playGate.enabled ? 'ENABLED' : `DISABLED:${playGate.reason}`}
              {' · '}status={snap.status}
              {' · '}owner={owner}
              {' · '}tick={String(snap.current_tick ?? '—')}
              {' · '}pos={snap.position_seconds.toFixed(3)}s / {duration.toFixed(3)}s
              {' · '}true_zero={String(snap.true_zero_at_cursor)}
              {' · '}gap={String(snap.gap_boundary)}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
              <button
                type="button"
                data-testid="hearing-sav4b-play"
                disabled={!playGate.enabled}
                onClick={() => { void onPlay(); }}
              >
                Play
              </button>
              <button type="button" data-testid="hearing-sav4b-pause" onClick={onPause}>
                Pause
              </button>
              <button type="button" data-testid="hearing-sav4b-stop" onClick={onStop}>
                Stop
              </button>
              <label className="subtle" data-testid="hearing-sav4b-seek">
                Seek tick{' '}
                <input
                  type="number"
                  data-testid="hearing-sav4b-seek-input"
                  disabled={!playGate.enabled}
                  defaultValue={Number(seg?.first_tick ?? 0)}
                  onBlur={(e) => onSeekTick(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') onSeekTick((e.target as HTMLInputElement).value);
                  }}
                  style={{ width: 72 }}
                />
              </label>
            </div>
            {!playGate.enabled ? (
              <div className="subtle" data-testid="hearing-sav4b-disabled-reason">
                Offline playback unavailable: {playGate.reason}
              </div>
            ) : null}
            <div className="subtle" data-testid="hearing-sav4b-no-export">
              No WAV / PCM / download export in SAV4B.
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
