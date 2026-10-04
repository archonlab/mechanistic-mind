/**
 * SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1
 * Researcher causal comparison over ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1.
 * Visual only — no playback, no LPS/phenotype recompute.
 */
import { useState } from 'react';
import {
  BAND_COUNT,
  SAV3_A3_BADGE,
  SAV3_A4_BADGE,
  SAV3_A5_BADGE,
  SAV3_CAPABILITY,
  SAV3_PROFILE,
  SAV3_RENDER_BADGE,
  SAV3_SCHEMA,
  SAV3_TITLE,
  SAV3_WARNING,
  a3BarWidthPx,
  a5BarWidthPx,
  asymmetryA5,
  bandRowFromTrace,
  isFiniteNum,
  num,
  totalActivation,
  transformPass,
} from './sav3Comparison.ts';

function fmt(v: unknown, digits = 4): string {
  if (!isFiniteNum(v)) return 'UNAVAILABLE';
  return Number(v).toFixed(digits);
}

function MiniBar({
  width,
  overflow,
  title,
  tone,
}: {
  width: number;
  overflow?: boolean;
  title: string;
  tone: string;
}) {
  return (
    <div
      title={title}
      style={{
        width: 52,
        height: 8,
        background: 'rgba(127,127,127,0.2)',
        position: 'relative',
        display: 'inline-block',
        verticalAlign: 'middle',
      }}
      data-display-derived="true"
    >
      <div
        style={{
          width,
          height: 8,
          background: overflow ? '#c66' : tone,
          maxWidth: 52,
        }}
      />
      {overflow ? (
        <span className="subtle" style={{ fontSize: 9, marginLeft: 2 }}>
          OVERFLOW
        </span>
      ) : null}
    </div>
  );
}

export function SelectedOrganismPhysicalFieldComparisonPanel({
  frame,
}: {
  frame: any;
}) {
  const [open, setOpen] = useState(false);
  const world = frame?.world;
  const sav3 = world?.selected_organism_physical_field_comparison;
  const sav1 = world?.selected_organism_auditory_view;
  const selectedAgent = sav3?.selected_agent_id ?? sav1?.selected_agent_id ?? frame?.header?.selected_agent_id ?? null;

  if (!sav3 && !world?.organism_auditory_transformation_trace && !sav1) {
    return null;
  }

  const status = String(sav3?.status || sav3?.availability || 'TRACE_NOT_YET_AVAILABLE');
  const tr = sav3?.latest_for_selected || null;
  const available = status === 'TRACE_AVAILABLE' || status === 'TRACE_MISMATCH';
  const a3 = tr?.a3 || {};
  const a4 = tr?.a4 || {};
  const a5 = tr?.a5 || {};
  const resid = transformPass(a4.transform_residual);
  const leftA5 = Array.isArray(a5.left_receptor_channels) ? a5.left_receptor_channels : [];
  const rightA5 = Array.isArray(a5.right_receptor_channels) ? a5.right_receptor_channels : [];
  const asym = asymmetryA5(leftA5, rightA5);
  const clipUpper = num(a4.clip_upper, 1);

  return (
    <div
      className="panel hearing-section sav3-comparison"
      data-testid="sav3-physical-field-comparison"
      data-schema={SAV3_SCHEMA}
      data-capability={SAV3_CAPABILITY}
      data-profile={SAV3_PROFILE}
      style={{ marginTop: 8 }}
    >
      <button
        type="button"
        data-testid="sav3-toggle"
        onClick={() => setOpen((v) => !v)}
        style={{ border: 0, background: 'transparent', padding: 0, cursor: 'pointer', fontWeight: 700, textAlign: 'left' }}
      >
        {SAV3_TITLE} {open ? '▾' : '▸'}
      </button>
      <div className="subtle" data-testid="sav3-warning" style={{ marginTop: 4 }}>
        {sav3?.warning_label || SAV3_WARNING}
      </div>
      <div className="subtle" data-testid="sav3-status">
        status={status} · agent={String(selectedAgent || '—')} · retained={sav3?.retained_count ?? '—'}/{sav3?.history_capacity ?? '—'} · mismatches={sav3?.mismatch_count ?? '—'} · evicted={sav3?.evicted_count ?? '—'}
      </div>

      {open ? (
        <div style={{ marginTop: 8 }} data-testid="sav3-body">
          {!available || !tr ? (
            <div className="subtle" data-testid="sav3-unavailable">
              {status === 'EXPERIMENTER_AUDITORY_COMPARISON_NOT_AVAILABLE'
                ? 'EXPERIMENTER_AUDITORY_COMPARISON_NOT_AVAILABLE'
                : status === 'LEGACY_TRACE_UNAVAILABLE' || status === 'SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_UNAVAILABLE_LEGACY_EVIDENCE'
                  ? 'LEGACY: A3/A4 comparison unavailable (do not invert A5)'
                  : sav1?.latest_for_selected?.availability === 'AVAILABLE'
                    ? 'A5 available via SAV1 · A3/A4 comparison UNAVAILABLE (no compatible trace)'
                    : `Comparison unavailable · ${status}`}
              <div style={{ marginTop: 4 }}>{sav3?.passive_probe_note}</div>
            </div>
          ) : (
            <>
              {/* Causal ladder */}
              <div data-testid="sav3-causal-ladder" className="subtle" style={{ marginBottom: 8 }}>
                <div><strong>1. A3 RAW RECEPTOR FIELD</strong> · {SAV3_A3_BADGE}</div>
                <div><strong>2. A4 PHENOTYPE TRANSFORM</strong> · {SAV3_A4_BADGE}</div>
                <div><strong>3. A5 DELIVERED TO ORGANISM</strong> · {SAV3_A5_BADGE}</div>
                <div data-testid="sav3-render-badge">{SAV3_RENDER_BADGE}</div>
              </div>

              <div className="subtle" data-testid="sav3-meta" style={{ wordBreak: 'break-word' }}>
                agent={tr.agent_id} · body={tr.body_id} · recv_tick={tr.reception_tick} · obs_tick={tr.observation_tick} · delay={tr.causal_delay_ticks}
                <br />
                trace={String(tr.trace_id || '').slice(0, 28)}… · sav1={String(tr.sav1_receipt_id || '').slice(0, 28)}…
                <br />
                obs_key={String(tr.observation_key || '').slice(0, 40)}
                <br />
                formula={sav3?.formula || 'A5 = clip(A3 / sensor_scale, lower, upper)'} · scale={fmt(a4.sensor_scale)} · clip=[{fmt(a4.clip_lower, 2)}, {fmt(a4.clip_upper, 2)}]
                <br />
                residual max={fmt(resid.max, 6)} · tol={fmt(resid.tol, 6)} ·{' '}
                <span data-testid="sav3-transform-status">{resid.pass ? 'PASS' : 'MISMATCH'}</span>
                <br />
                accepted_contributors={a3.accepted_contributor_count ?? '—'} · clip_count={a4.clipping_count ?? '—'}
                <br />
                {sav3?.a2_gate_status} · {sav3?.contributor_decomposition_status}
                <br />
                {sav3?.passive_probe_note}
              </div>

              {/* Matrix */}
              <div data-testid="sav3-matrix" className="sav3-matrix" style={{ marginTop: 8, overflowX: 'hidden' }}>
                <div className="subtle" style={{ fontWeight: 700 }}>SIX-BAND A3→A5 MATRIX · A5 scale [0,1] fixed · A3 unit=clip_upper (+OVERFLOW)</div>
                {Array.from({ length: BAND_COUNT }, (_, i) => {
                  const row = bandRowFromTrace(tr, i);
                  const lA3 = a3BarWidthPx(row.a3L, clipUpper, 48);
                  const rA3 = a3BarWidthPx(row.a3R, clipUpper, 48);
                  const lSc = a3BarWidthPx(row.scaledL, clipUpper, 48);
                  const rSc = a3BarWidthPx(row.scaledR, clipUpper, 48);
                  return (
                    <div
                      key={row.band}
                      data-testid={`sav3-band-${i}`}
                      className="sav3-band-row"
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 6,
                        marginTop: 6,
                        borderTop: '1px solid rgba(127,127,127,0.25)',
                        paddingTop: 4,
                      }}
                    >
                      <div data-testid={`sav3-band-${i}-left`}>
                        <div className="subtle" style={{ fontWeight: 600 }}>{row.band} LEFT</div>
                        <div className="subtle">A3={fmt(row.a3L)} <MiniBar width={lA3.width} overflow={lA3.overflow} title={`A3L ${fmt(row.a3L)}`} tone="#6af" /></div>
                        <div className="subtle">scaled={fmt(row.scaledL)} <MiniBar width={lSc.width} overflow={lSc.overflow} title={`scaledL ${fmt(row.scaledL)}`} tone="#9c6" /></div>
                        <div className="subtle">A5={fmt(row.a5L)} <MiniBar width={a5BarWidthPx(row.a5L, 48)} title={`A5L ${fmt(row.a5L)}`} tone="#c6a" /></div>
                        <div className="subtle" data-testid={`sav3-band-${i}-clip-l`}>clip={row.clipL} · res={fmt(row.resL, 6)}</div>
                      </div>
                      <div data-testid={`sav3-band-${i}-right`}>
                        <div className="subtle" style={{ fontWeight: 600 }}>{row.band} RIGHT</div>
                        <div className="subtle">A3={fmt(row.a3R)} <MiniBar width={rA3.width} overflow={rA3.overflow} title={`A3R ${fmt(row.a3R)}`} tone="#6af" /></div>
                        <div className="subtle">scaled={fmt(row.scaledR)} <MiniBar width={rSc.width} overflow={rSc.overflow} title={`scaledR ${fmt(row.scaledR)}`} tone="#9c6" /></div>
                        <div className="subtle">A5={fmt(row.a5R)} <MiniBar width={a5BarWidthPx(row.a5R, 48)} title={`A5R ${fmt(row.a5R)}`} tone="#c6a" /></div>
                        <div className="subtle" data-testid={`sav3-band-${i}-clip-r`}>clip={row.clipR} · res={fmt(row.resR, 6)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="subtle" data-testid="sav3-asymmetry" style={{ marginTop: 8 }}>
                LEFT/RIGHT ASYMMETRY (RESEARCHER-DERIVED COMPARISON · not binaural localization)
                <br />
                ΣA5_L={fmt(totalActivation(leftA5))} · ΣA5_R={fmt(totalActivation(rightA5))} · Δ bands=[{asym.map((d) => fmt(d, 3)).join(', ')}]
              </div>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
