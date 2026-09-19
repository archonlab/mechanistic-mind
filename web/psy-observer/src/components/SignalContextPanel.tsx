/** Observer-only Signal Context Interpreter panel (BETA2-SIGINT-01 / 02 / 03). */
import { useState } from 'react';
import {
  analyzeSignalContextRun,
  getSignalContextEpisode,
  getSignalIntervention,
  listCognitiveForensics,
  listInteractionEpisodes,
  listSignalInterventions,
  listSignalRepertoire,
  listSignalSpecimens,
  replayInteractionEpisode,
  replaySignalSpecimen,
  saveSignalSpecimen,
} from '../api/client';

const REF_RUN = 'psyweb-20260918T021911.211579Z-b3cd1135';

function KV({ name, value }: { name: string; value: unknown }) {
  const v =
    value === null || value === undefined
      ? 'NOT AVAILABLE'
      : typeof value === 'object'
        ? JSON.stringify(value)
        : String(value);
  return (
    <div className="kv">
      <span>{name}</span>
      <b>{v}</b>
    </div>
  );
}

export function SignalContextPanel({
  live,
  selectedEvent,
}: {
  live?: any;
  selectedEvent?: any;
}) {
  const [analysis, setAnalysis] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [selectedEp, setSelectedEp] = useState<any>(null);
  const [interventions, setInterventions] = useState<any[]>([]);
  const [interventionDetail, setInterventionDetail] = useState<any>(null);
  const [specimen, setSpecimen] = useState<any>(null);
  const [specimens, setSpecimens] = useState<any[]>([]);
  const [replayTarget, setReplayTarget] = useState<'SELF' | 'PEER' | 'LOCATION'>('PEER');
  const [replayMode, setReplayMode] = useState<'EXACT' | 'ALTER_AMPLITUDE' | 'ALTER_CHANNEL' | 'DELAY'>(
    'EXACT',
  );
  const [replayResult, setReplayResult] = useState<any>(null);
  const [repertoire, setRepertoire] = useState<any>(null);
  const [repFilter, setRepFilter] = useState('ALL');
  const [interactionEps, setInteractionEps] = useState<any>(null);
  const [selectedEpisode, setSelectedEpisode] = useState<any>(null);
  const [episodeReplayMode, setEpisodeReplayMode] = useState('FULL');
  const [episodeReplayResult, setEpisodeReplayResult] = useState<any>(null);
  const [forensics, setForensics] = useState<any>(null);
  const [selectedForensic, setSelectedForensic] = useState<any>(null);

  const episodes = Array.isArray(live?.recent_episodes) ? live.recent_episodes : [];
  const isRecv =
    String(selectedEvent?.type || selectedEvent?.kind || '').includes('SIGNAL_RECEIVED');
  const isEmit =
    String(selectedEvent?.type || selectedEvent?.kind || '').includes('SIGNAL_EMITTED') ||
    String(selectedEvent?.type || selectedEvent?.kind || '').includes('EMITTED');

  async function runAnalyze(runId = REF_RUN) {
    setBusy(true);
    setErr(null);
    try {
      const r = await analyzeSignalContextRun(runId, {
        max_timeline_rows: 20000,
        max_events: 120000,
        max_episode_details: 36,
      });
      if (!r.accepted) throw new Error(r.error || 'analysis failed');
      setAnalysis(r);
      const first = (r.episode_details || [])[0];
      setSelectedEp(first || null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function inspectLiveEpisode(id: string) {
    try {
      const r = await getSignalContextEpisode(id);
      if (r.accepted) setSelectedEp({ signal_episode: r.episode, LIVE: true, ...r });
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  }

  async function loadInterventions() {
    setBusy(true);
    setErr(null);
    try {
      const r = await listSignalInterventions();
      setInterventions(r.experiments || []);
      if ((r.experiments || [])[0]) {
        const d = await getSignalIntervention(r.experiments[0].id);
        setInterventionDetail(d);
      }
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function openIntervention(id: string) {
    setBusy(true);
    try {
      const d = await getSignalIntervention(id);
      setInterventionDetail(d);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function saveSelectedAsSpecimen() {
    if (!selectedEvent) {
      setErr('Select a natural emission event first');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await saveSignalSpecimen(selectedEvent);
      if (!r.accepted) throw new Error(r.error || 'save failed');
      setSpecimen(r.specimen);
      const lib = await listSignalSpecimens({ limit: 32 });
      setSpecimens(lib.specimens || []);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function loadSpecimens() {
    setBusy(true);
    try {
      const r = await listSignalSpecimens({ limit: 32 });
      setSpecimens(r.specimens || []);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function doReplay() {
    const sid = specimen?.specimen_id;
    if (!sid) {
      setErr('Save or select a specimen first');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await replaySignalSpecimen({
        specimen_id: sid,
        target: replayTarget,
        mode: replayMode,
        amplitude_scale: replayMode === 'ALTER_AMPLITUDE' ? 0.5 : 1.0,
      });
      setReplayResult(r);
      if (!r.accepted) setErr(r.error || 'replay rejected');
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function loadRepertoire(filter = repFilter) {
    setBusy(true);
    setErr(null);
    try {
      const r = await listSignalRepertoire({ filter, limit: 48 });
      setRepertoire(r);
      setRepFilter(filter);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function loadEpisodes() {
    setBusy(true);
    setErr(null);
    try {
      const r = await listInteractionEpisodes({ limit: 24 });
      setInteractionEps(r);
      if ((r.episodes || [])[0]) setSelectedEpisode(r.episodes[0]);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function doEpisodeReplay() {
    if (!selectedEpisode) {
      setErr('Select an interaction episode first');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await replayInteractionEpisode({
        episode: selectedEpisode,
        mode: episodeReplayMode,
      });
      setEpisodeReplayResult(r);
      if (!r.accepted) setErr(r.error || 'episode replay rejected');
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function loadForensics() {
    setBusy(true);
    setErr(null);
    try {
      const r = await listCognitiveForensics({ limit: 8 });
      setForensics(r);
      if ((r.trials || [])[0]) setSelectedForensic(r.trials[0]);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  const detail = selectedEp;
  const ep = detail?.signal_episode || detail?.episode;
  const delta = detail?.cognition_delta;
  const controls = detail?.matched_controls;
  const verdict = detail?.EVIDENCE_VERDICT || detail?.matched_comparison?.evidence;

  return (
    <div className="science-card" style={{ marginTop: 12 }}>
      <h3>Signal Context Interpreter</h3>
      <div className="subtle">
        PHYSICAL SIGNAL → measurable context → deltas → matched controls. Not communication.
      </div>
      <div className="subtle" style={{ marginTop: 4 }}>
        PHYSICAL FIELD = runtime ground truth · EMPIRICAL association ≠ causal link · Observer-only
      </div>

      <div className="toolbar-row" style={{ marginTop: 8, gap: 8, flexWrap: 'wrap' }}>
        <button disabled={busy} onClick={() => runAnalyze()}>
          {busy ? 'Analyzing…' : 'ANALYZE seed-17 reference run'}
        </button>
        <span className="subtle">
          LIVE episodes: {live?.n_episodes ?? 0} · buffered recv: {live?.n_receptions_buffered ?? 0}
        </span>
      </div>
      {err ? <div className="availability" style={{ marginTop: 6 }}>{err}</div> : null}

      {isRecv ? (
        <div style={{ marginTop: 8 }}>
          <h4>Selected PHYSICAL_SIGNAL_RECEIVED</h4>
          <KV name="Tick" value={selectedEvent?.tick} />
          <KV name="Receiver" value={selectedEvent?.agent_id || selectedEvent?.receiver_agent_id} />
          <KV name="Attribution" value={selectedEvent?.evidence?.source_attribution} />
          <KV name="local.FIELD_A" value={selectedEvent?.evidence?.['local.FIELD_A']} />
          <KV name="local.FIELD_B" value={selectedEvent?.evidence?.['local.FIELD_B']} />
          <div className="subtle">
            Open ANALYZE for PRE/POST + matched controls around this tick’s episode family.
          </div>
        </div>
      ) : null}

      {isEmit || selectedEvent ? (
        <div style={{ marginTop: 12, paddingTop: 8, borderTop: '1px solid rgba(148,163,184,0.25)' }}>
          <h3>EXPERIMENTER INTERVENTION — Natural signal specimen</h3>
          <div className="subtle">
            Physical recording only. Not a message. LIVE replay = UNCONTROLLED_LIVE_REPLAY.
          </div>
          <div className="toolbar-row" style={{ marginTop: 8, gap: 8, flexWrap: 'wrap' }}>
            <button type="button" disabled={busy || !selectedEvent} onClick={saveSelectedAsSpecimen}>
              SAVE AS SIGNAL SPECIMEN
            </button>
            <button type="button" disabled={busy} onClick={loadSpecimens}>
              Load specimen library
            </button>
          </div>
          {specimen ? (
            <div style={{ marginTop: 8 }}>
              <h4>NATURAL SIGNAL SPECIMEN</h4>
              <KV name="specimen ID" value={specimen.specimen_id} />
              <KV name="source tick" value={specimen.source_tick} />
              <KV
                name="source agent/body"
                value={`${specimen.emitter_agent_id} / ${specimen.emitter_body_id}`}
              />
              <KV name="FIELD channel" value={specimen.channel} />
              <KV name="amplitude" value={specimen.amplitude} />
              <KV name="reconstruction" value={specimen.reconstruction_completeness} />
              <KV name="provenance" value={specimen.provenance} />
            </div>
          ) : null}
          {specimens.length ? (
            <div className="event-list" style={{ maxHeight: 120, marginTop: 8 }}>
              {specimens.slice(0, 12).map((s: any) => (
                <button key={s.specimen_id} type="button" onClick={() => setSpecimen(s)}>
                  <span>t{s.source_tick}</span>
                  <b>FIELD_{s.channel}</b>
                  <small>
                    {s.specimen_id.slice(0, 12)} · amp={String(s.amplitude)} ·{' '}
                    {s.reconstruction_completeness}
                  </small>
                </button>
              ))}
            </div>
          ) : null}
          <div style={{ marginTop: 10 }}>
            <h4>REPLAY</h4>
            <div className="subtle">Target</div>
            <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {(['SELF', 'PEER', 'LOCATION'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  disabled={busy}
                  onClick={() => setReplayTarget(t)}
                  style={{ opacity: replayTarget === t ? 1 : 0.65 }}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="subtle" style={{ marginTop: 6 }}>
              Mode
            </div>
            <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {(['EXACT', 'ALTER_AMPLITUDE', 'ALTER_CHANNEL', 'DELAY'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  disabled={busy}
                  onClick={() => setReplayMode(m)}
                  style={{ opacity: replayMode === m ? 1 : 0.65 }}
                >
                  {m.replace('_', ' ')}
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={busy || !specimen}
              onClick={doReplay}
              style={{ marginTop: 8 }}
            >
              ↻ REPLAY SIGNAL
            </button>
            {replayResult ? (
              <div style={{ marginTop: 8 }}>
                <KV name="status" value={replayResult.status} />
                <KV name="trial ID" value={replayResult.trial_id} />
                <KV name="intervention tick" value={replayResult.tick} />
                <KV name="target" value={replayResult.target} />
                <KV name="mode" value={replayResult.mode} />
                <KV name="channel" value={replayResult.queue?.channel} />
                <KV name="amplitude" value={replayResult.queue?.amplitude} />
                <KV name="n_cells" value={replayResult.queue?.n_cells} />
                <div className="subtle">{replayResult.note}</div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {episodes.length ? (
        <>
          <h4 style={{ marginTop: 10 }}>LIVE episodes (bounded)</h4>
          <div className="event-list">
            {episodes.slice(-8).reverse().map((e: any) => (
              <button key={e.episode_id} type="button" onClick={() => inspectLiveEpisode(e.episode_id)}>
                <span>
                  t{e.start_tick}–{e.end_tick}
                </span>
                <b>{e.channel}</b>
                <small>
                  {e.receiver_agent_id} · peak={Number(e.intensity?.peak).toFixed(3)} · {e.attribution}
                </small>
              </button>
            ))}
          </div>
        </>
      ) : (
        <div className="subtle" style={{ marginTop: 8 }}>
          No LIVE episodes yet — run TwoAgent with experimental physical signal, or ANALYZE a saved run.
        </div>
      )}

      {analysis ? (
        <div style={{ marginTop: 10 }}>
          <h4>Analysis summary</h4>
          <KV name="Episodes" value={analysis.n_episodes} />
          <KV name="Detailed" value={analysis.n_episode_details} />
          <KV name="Matched associations" value={analysis.matched_association_count} />
          <KV name="Channels" value={analysis.channel_counts} />
          <KV name="Patterns" value={(analysis.patterns || []).length} />
          <div className="event-list" style={{ maxHeight: 160 }}>
            {(analysis.episode_details || []).slice(0, 24).map((d: any) => {
              const e = d.signal_episode || {};
              return (
                <button key={e.episode_id} type="button" onClick={() => setSelectedEp(d)}>
                  <span>t{e.peak_tick}</span>
                  <b>{e.channel}</b>
                  <small>
                    {e.receiver_agent_id} · {d.EVIDENCE_VERDICT} · peak=
                    {Number(e.intensity?.peak).toFixed(3)}
                  </small>
                </button>
              );
            })}
          </div>
          {(analysis.patterns || []).slice(0, 6).map((p: any) => (
            <div key={p.pattern_id} className="subtle" style={{ marginTop: 4 }}>
              {p.pattern_id}: n={p.episodes} · {p.SIGNAL?.channel} · evidence={p.evidence}
              {' · '}actionΔ {Number(p.POST?.requested_direction_changed_frac || 0).toFixed(2)}
              {' vs ctrl '}
              {p.matched_controls?.mean_action_change_rate == null
                ? '—'
                : Number(p.matched_controls.mean_action_change_rate).toFixed(2)}
            </div>
          ))}
        </div>
      ) : null}

      {ep ? (
        <div style={{ marginTop: 12, paddingTop: 8, borderTop: '1px solid #334155' }}>
          <h4>SIGNAL EPISODE</h4>
          <KV name="ID" value={ep.episode_id} />
          <KV name="Receiver" value={ep.receiver_agent_id} />
          <KV name="Channel" value={ep.channel} />
          <KV name="Ticks" value={`${ep.start_tick}–${ep.end_tick} (peak ${ep.peak_tick})`} />
          <KV name="Intensity peak/mean" value={`${ep.intensity?.peak} / ${ep.intensity?.mean}`} />
          <KV name="Attribution" value={ep.attribution} />
          <KV name="Triggers" value={ep.trigger_composition} />
          <KV name="Cross-agent frac" value={ep.cross_agent_contribution_fraction} />
          <KV name="Self frac" value={ep.self_contribution_fraction} />

          {delta ? (
            <>
              <h4>COGNITION / ACTION DELTA</h4>
              <KV name="PRE action" value={delta.PRE?.action} />
              <KV name="PRE source" value={delta.PRE?.selection_source} />
              <KV name="POST action" value={delta.POST?.action} />
              <KV name="POST source" value={delta.POST?.selection_source} />
              <KV name="Δ action" value={delta.DELTA?.action_changed} />
              <KV name="Δ selection source" value={delta.DELTA?.selection_source_changed} />
              <KV name="Evidence" value={delta.EVIDENCE?.reception_to_cognitive_delta} />
              <div className="subtle">{delta.coverage?.fake_zero_warning}</div>
            </>
          ) : (
            <div className="subtle">Matched PRE/POST available in ANALYZE RESULTS path only.</div>
          )}

          {detail?.action_geometry ? (
            <>
              <h4>REQUESTED VS REALIZED / GEOMETRY</h4>
              <KV name="Interpretation" value={detail.action_geometry.interpretation} />
              <KV
                name="signal→action causality"
                value={detail.action_geometry.evidence?.signal_to_action_causality}
              />
            </>
          ) : null}

          {controls ? (
            <>
              <h4>MATCHED CONTROLS</h4>
              <KV name="Quality" value={controls.match_quality} />
              <KV name="Count" value={controls.n_controls} />
              <KV name="Verdict" value={verdict} />
            </>
          ) : null}

          {detail?.provenance ? (
            <>
              <h4>PROVENANCE</h4>
              <KV name="emission→reception" value={detail.provenance.emission_to_field_to_reception} />
              <KV name="reception→observation" value={detail.provenance.reception_to_observation} />
              <KV name="reception→cognition" value={detail.provenance.reception_to_cognitive_change} />
              <div className="subtle">{detail.provenance.note}</div>
            </>
          ) : null}
        </div>
      ) : null}

      <div style={{ marginTop: 16, borderTop: '1px solid rgba(148,163,184,0.25)', paddingTop: 12 }}>
        <h3>NATURAL SIGNAL REPERTOIRE (SIGINT-04)</h3>
        <div className="subtle">
          Physical families × screen results. Not meanings. On-demand — not in LIVE frames.
        </div>
        <div className="toolbar-row" style={{ marginTop: 8, gap: 6, flexWrap: 'wrap' }}>
          {(
            [
              'ALL',
              'UNTESTED',
              'INERT_UNDER_TESTED_CONTEXTS',
              'COGNITION_CANDIDATES',
              'ACTION_CANDIDATES',
              'TRAJECTORY_CANDIDATES',
            ] as const
          ).map((f) => (
            <button
              key={f}
              type="button"
              disabled={busy}
              onClick={() => loadRepertoire(f)}
              style={{ opacity: repFilter === f ? 1 : 0.65 }}
            >
              {f.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
        {repertoire?.note ? <div className="subtle" style={{ marginTop: 6 }}>{repertoire.note}</div> : null}
        {repertoire?.experiment_dir ? (
          <div className="subtle" style={{ marginTop: 4 }}>Artifact: {repertoire.experiment_dir}</div>
        ) : null}
        {repertoire?.families?.length ? (
          <div className="subtle" style={{ marginTop: 6 }}>
            Families: {repertoire.families.length} · showing {repertoire.n_specimens}
          </div>
        ) : null}
        {repertoire?.specimens?.length ? (
          <div className="event-list" style={{ maxHeight: 200, marginTop: 8 }}>
            {repertoire.specimens.map((s: any) => (
              <button
                key={s.specimen_id}
                type="button"
                onClick={() =>
                  setSpecimen({
                    specimen_id: s.specimen_id,
                    channel: s.channel,
                    amplitude: s.amplitude,
                    source_tick: s.source_tick,
                    emitter_agent_id: s.emitter_agent_id,
                    emitter_body_id: '—',
                    reconstruction_completeness: s.reconstruction_completeness,
                    provenance: 'REPERTOIRE',
                    trigger: s.trigger,
                  })
                }
              >
                <span>t{s.source_tick}</span>
                <b>FIELD_{s.channel}</b>
                <small>
                  {s.evidence_class || '—'} · L2={s.fingerprint?.selection_source || '—'} ·{' '}
                  {(s.tags || []).join(',') || 'no-tag'}
                </small>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div style={{ marginTop: 16, borderTop: '1px solid rgba(148,163,184,0.25)', paddingTop: 12 }}>
        <h3>INTERACTION EPISODES (SIGINT-05)</h3>
        <div className="subtle">
          Temporally structured physical sequences. Not dialogue. Coupling ≠ following.
        </div>
        <div className="toolbar-row" style={{ marginTop: 8, gap: 8 }}>
          <button type="button" disabled={busy} onClick={loadEpisodes}>
            {busy ? 'Loading…' : 'Load interaction episodes'}
          </button>
        </div>
        {interactionEps?.note ? <div className="subtle" style={{ marginTop: 6 }}>{interactionEps.note}</div> : null}
        {interactionEps?.reference ? (
          <div className="subtle" style={{ marginTop: 6 }}>
            Reference t{interactionEps.reference.start_tick}–{interactionEps.reference.end_tick} · reconstr=
            {interactionEps.reference.reconstruction}
          </div>
        ) : null}
        {selectedEpisode?.temporal_strip || interactionEps?.reference?.temporal_strip ? (
          <div style={{ marginTop: 8, fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
            <div className="subtle">Temporal strip (physical emissions)</div>
            {(() => {
              const strip =
                selectedEpisode?.temporal_strip || interactionEps?.reference?.temporal_strip || {};
              const ticks = strip.ticks || [];
              return (
                <div style={{ overflowX: 'auto' }}>
                  <div>tick: {ticks.join(' ')}</div>
                  <div>A: {(strip.A || []).map((x: string) => x || '·').join('  ')}</div>
                  <div>B: {(strip.B || []).map((x: string) => x || '·').join('  ')}</div>
                  <div>FIELD: {(strip.FIELD || []).map((x: string) => x || '·').join(' ')}</div>
                </div>
              );
            })()}
          </div>
        ) : null}
        {interactionEps?.episodes?.length ? (
          <div className="event-list" style={{ maxHeight: 160, marginTop: 8 }}>
            {interactionEps.episodes.map((e: any) => (
              <button key={e.episode_id} type="button" onClick={() => setSelectedEpisode(e)}>
                <span>
                  t{e.start_tick}–{e.end_tick}
                </span>
                <b>{e.reconstruction}</b>
                <small>
                  n={e.n_components} · trials={e.n_trials} · L2={String(e.levels?.L2_cognition)} ·
                  L5={String(e.levels?.L5_coupling)}
                </small>
              </button>
            ))}
          </div>
        ) : null}
        {selectedEpisode ? (
          <div style={{ marginTop: 8 }}>
            <KV name="episode" value={selectedEpisode.episode_id} />
            <KV name="reconstruction" value={selectedEpisode.reconstruction} />
            <KV name="components" value={selectedEpisode.n_components} />
            <div className="subtle" style={{ marginTop: 6 }}>
              REPLAY EPISODE mode
            </div>
            <div className="toolbar-row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {(['FULL', 'A_TO_B_ONLY', 'B_TO_A_ONLY', 'SHUFFLED', 'REVERSED'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  disabled={busy}
                  onClick={() => setEpisodeReplayMode(m)}
                  style={{ opacity: episodeReplayMode === m ? 1 : 0.65 }}
                >
                  {m}
                </button>
              ))}
            </div>
            <button type="button" disabled={busy} onClick={doEpisodeReplay} style={{ marginTop: 8 }}>
              REPLAY EPISODE
            </button>
            {episodeReplayResult ? (
              <div style={{ marginTop: 6 }}>
                <KV name="status" value={episodeReplayResult.status} />
                <KV name="injected" value={episodeReplayResult.n_injected_this_step} />
                <div className="subtle">{episodeReplayResult.note}</div>
              </div>
            ) : null}
          </div>
        ) : null}

        <div style={{ marginTop: 12 }}>
          <h4>COGNITIVE DIVERGENCE FORENSICS (SIGINT-06)</h4>
          <div className="subtle">On-demand. Explains action equality despite cognitive divergence.</div>
          <button type="button" disabled={busy} onClick={loadForensics} style={{ marginTop: 6 }}>
            Load Level-2 forensics
          </button>
          {forensics?.note ? <div className="subtle" style={{ marginTop: 4 }}>{forensics.note}</div> : null}
          {forensics?.verdicts ? (
            <div className="subtle" style={{ marginTop: 4 }}>
              bottleneck={String(forensics.verdicts.SIGNAL_TO_ACTION_BOTTLENECK)} · action_conv=
              {String(forensics.verdicts.ACTION_CONVERGENCE_WITH_INTERNAL_DIVERGENCE)}
            </div>
          ) : null}
          {forensics?.trials?.length ? (
            <div className="event-list" style={{ maxHeight: 120, marginTop: 8 }}>
              {forensics.trials.map((t: any, i: number) => (
                <button key={i} type="button" onClick={() => setSelectedForensic(t)}>
                  <span>
                    t{t.hit?.start_tick}–{t.hit?.end_tick}
                  </span>
                  <b>{t.bottleneck?.classification || '—'}</b>
                  <small>code={t.bottleneck?.best_supported?.code || '—'}</small>
                </button>
              ))}
            </div>
          ) : null}
          {selectedForensic?.parallel_lanes ? (
            <div style={{ marginTop: 8, fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
              <div className="subtle">Parallel lanes @ tick {selectedForensic.parallel_lanes.branch_tick}</div>
              <div>
                FIELD&nbsp;&nbsp;CTRL {String(selectedForensic.parallel_lanes.CONTROL?.FIELD)}&nbsp;&nbsp;REPLAY{' '}
                {String(selectedForensic.parallel_lanes.REPLAY?.FIELD)}
              </div>
              <div>
                SOURCE CTRL {String(selectedForensic.parallel_lanes.CONTROL?.SOURCE)}&nbsp;&nbsp;REPLAY{' '}
                {String(selectedForensic.parallel_lanes.REPLAY?.SOURCE)}
              </div>
              <div>
                WINNER CTRL {String(selectedForensic.parallel_lanes.CONTROL?.WINNER)}&nbsp;&nbsp;REPLAY{' '}
                {String(selectedForensic.parallel_lanes.REPLAY?.WINNER)}
              </div>
              <div>
                ACTION CTRL {String(selectedForensic.parallel_lanes.CONTROL?.ACTION)}&nbsp;&nbsp;REPLAY{' '}
                {String(selectedForensic.parallel_lanes.REPLAY?.ACTION)}
              </div>
              {selectedForensic.parallel_lanes.divergence_dies_at_action ? (
                <div className="subtle">DIVERGENCE DIES HERE ↑ (action equal; source differs)</div>
              ) : null}
              <div className="subtle" style={{ marginTop: 4 }}>
                {selectedForensic.bottleneck?.best_supported?.text}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div style={{ marginTop: 16, borderTop: '1px solid rgba(148,163,184,0.25)', paddingTop: 12 }}>
        <h3>Signal intervention (SIGINT-02)</h3>
        <div className="subtle">
          Offline matched-branch FIELD interventions. Not live WORLD injection. Not communication.
        </div>
        <div className="row" style={{ gap: 8, marginTop: 8 }}>
          <button type="button" disabled={busy} onClick={loadInterventions}>
            {busy ? 'Loading…' : 'Load intervention experiments'}
          </button>
        </div>
        {interventions.length ? (
          <div style={{ marginTop: 8 }}>
            {interventions.slice(0, 8).map((ex) => (
              <button
                key={ex.id}
                type="button"
                className="subtle"
                style={{ display: 'block', marginBottom: 4 }}
                onClick={() => openIntervention(ex.id)}
              >
                {ex.id}
              </button>
            ))}
          </div>
        ) : null}
        {interventionDetail?.accepted ? (
          <div style={{ marginTop: 8 }}>
            <KV name="Experiment" value={interventionDetail.experiment_id} />
            <KV
              name="Receiver sensitivity"
              value={interventionDetail.report?.verdicts?.RECEIVER_SIDE_CAUSAL_SIGNAL_SENSITIVITY}
            />
            <KV
              name="FIELD→ACTION"
              value={interventionDetail.report?.verdicts?.FIELD_TO_ACTION_CHANGE}
            />
            <KV
              name="FIELD→COGNITION"
              value={interventionDetail.report?.verdicts?.FIELD_TO_COGNITIVE_CHANGE}
            />
            <KV
              name="Learned communication"
              value={interventionDetail.report?.verdicts?.LEARNED_COMMUNICATION}
            />
            <KV
              name="Control/control determinism"
              value={interventionDetail.report?.verdicts?.CONTROL_CONTROL_DETERMINISM}
            />
            {(interventionDetail.first_divergence || []).slice(0, 3).map((d: any, i: number) => (
              <div key={i} className="subtle" style={{ marginTop: 6 }}>
                seed={d.seed} intervention firstΔ action=
                {d.divergences_vs_control?.INTERVENTION?.action ?? 'none'} obs=
                {d.divergences_vs_control?.INTERVENTION?.observation_field ?? 'none'}
              </div>
            ))}
            <div className="subtle" style={{ marginTop: 8 }}>
              Sham / wrong-channel / dose / context arms live in the experiment artifacts.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
