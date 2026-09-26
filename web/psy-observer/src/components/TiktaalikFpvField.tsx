/** Agent-centered FPV grid — canonical sample receipts, not a camera. */

import { useMemo, useState } from 'react';
import type { EyeLink, FpvSample } from './tiktaalikFpvModel';
import {
  contributionFill,
  falseColorRgb,
  gridIndex,
  sampleMatchesLink,
  spatialBinLabel,
} from './tiktaalikFpvModel';

type Props = {
  agentId: string;
  fpv: any;
  mode: 'OPTICAL' | 'CONTRIBUTION';
  link: EyeLink;
  onHoverSample: (s: FpvSample | null) => void;
};

export function TiktaalikFpvField({ agentId, fpv, mode, link, onHoverSample }: Props) {
  const radius = Math.max(1, Math.min(3, Number(fpv?.radius || 1)));
  const disc = String(fpv?.surface_discrimination || 'OFF').toUpperCase();
  const spatialMode = String(fpv?.spatial_vision || 'LEGACY').toUpperCase();
  const spatial = spatialMode !== 'LEGACY';
  const dim = 2 * radius + 1;
  const samples: FpvSample[] = Array.isArray(fpv?.samples) ? fpv.samples : [];
  const [picked, setPicked] = useState<FpvSample | null>(null);

  const cells = useMemo(() => {
    const map = new Map<string, FpvSample>();
    for (const s of samples) {
      const { row, col } = gridIndex(Number(s.fwd || 0), Number(s.left || 0), radius);
      const k = `${row},${col}`;
      const prev = map.get(k);
      if (!prev) {
        map.set(k, s);
        continue;
      }
      const rank = (x: FpvSample) => (x.status === 'accepted' ? 2 : x.status === 'own_cell_excluded' ? 3 : 1);
      if (rank(s) > rank(prev) || Number(s.final || 0) > Number(prev.final || 0)) map.set(k, s);
    }
    return map;
  }, [samples, radius]);

  return (
    <div className="fpv-field" data-testid={`tiktaalik-fpv-${agentId}`}>
      <div className="eye-title">{String(agentId).replace('_', ' ').toUpperCase()} FPV</div>
      <div className="subtle">{fpv?.honesty}</div>
      <div className="eye-meta">
        <strong>R={radius}</strong>
        <strong>FOV {fpv?.fov_deg ?? 120}°</strong>
        <strong>HEADING {fpv?.heading_source || '—'}</strong>
        <strong>SURFACE {disc}</strong>
        <strong>MAPPING {fpv?.optical_mapping || '—'}</strong>
        <strong>SPATIAL {fpv?.spatial_vision || 'LEGACY'}</strong>
        {spatial ? <strong>OCCLUDED {Number(fpv?.n_occluded || 0)}</strong> : null}
      </div>
      {disc === 'OFF' ? <div className="subtle">SURFACE CHANNELS ABSENT</div> : null}
      {disc === 'RICH' ? (
        <div className="subtle">FALSE-COLOR PROJECTION — C0/C1/C2 mapped to display RGB. Not cognition RGB labels.</div>
      ) : null}
      {picked ? (
        <details className="fpv-inspect" open>
          <summary>Sample debug · researcher-only · not agent-accessible as structured fields</summary>
          <div className="fpv-debug-row"><span>status</span><strong>{picked.status}</strong></div>
          <div className="fpv-debug-row"><span>angular bin</span><strong>{spatial ? (spatialBinLabel(picked) || '—') : (picked.sector || '—')}</strong></div>
          <div className="fpv-debug-row"><span>fwd / left</span><strong>{Number(picked.fwd).toFixed(3)} · {Number(picked.left).toFixed(3)}</strong></div>
          <div className="fpv-debug-row"><span>dist_f / illumination</span><strong>{String(picked.dist_f ?? '—')} · {String(picked.illumination ?? '—')}</strong></div>
          <div className="fpv-debug-row"><span>C0 / C1 / C2</span><strong>{String(picked.c0 ?? 'ABSENT')} · {String(picked.c1 ?? 'ABSENT')} · {String(picked.c2 ?? 'ABSENT')}</strong></div>
          <div className="fpv-debug-row"><span>body / composed / final</span><strong>{String(picked.body_optical ?? 0)} · {String(picked.composed ?? '—')} · {String(picked.final)}</strong></div>
          <div className="fpv-debug-row"><span>occlusion</span><strong>{picked.status === 'occluded' ? `YES by ${JSON.stringify(picked.occluded_by)}` : 'NO'}</strong></div>
          <div className="fpv-debug-row"><span>world cell</span><strong>{JSON.stringify(picked.world_cell)}</strong></div>
          {picked.temporal ? <div className="fpv-debug-row"><span>Δ</span><strong>{String(picked.temporal)}</strong></div> : null}
        </details>
      ) : (
        <details className="fpv-inspect">
          <summary>Sample debug · researcher-only · not agent-accessible as structured fields</summary>
          <div className="subtle">Select a cell. Diagnostic only.</div>
        </details>
      )}
      <div className="fpv-stage">
        <div className="fpv-compass">forward</div>
        <div
          className="fpv-grid"
          style={{ gridTemplateColumns: `repeat(${dim}, 1fr)`, gridTemplateRows: `repeat(${dim}, 1fr)` }}
        >
          {Array.from({ length: dim * dim }, (_, i) => {
            const row = Math.floor(i / dim);
            const col = i % dim;
            const s = cells.get(`${row},${col}`);
            const own = s?.status === 'own_cell_excluded' || (row === radius && col === radius && !s);
            const hl = s ? sampleMatchesLink(s, link) : false;
            const fill = !s
              ? 'transparent'
              : mode === 'OPTICAL'
                ? falseColorRgb(s, disc)
                : contributionFill(s, spatialMode);
            const cls = [
              'fpv-cell',
              s?.status || 'empty',
              own ? 'own' : '',
              hl ? 'linked' : '',
              s?.temporal || '',
            ].filter(Boolean).join(' ');
            return (
              <button
                key={i}
                type="button"
                className={cls}
                style={{ background: own ? '#111827' : fill }}
                title={s ? `${s.status} ${spatial ? spatialBinLabel(s) : (s.sector || '')} final=${s.final}${s.status === 'occluded' ? ' OCCLUDED' : ''}` : ''}
                onMouseEnter={() => { if (s) { setPicked(s); onHoverSample(s); } }}
                onMouseLeave={() => { onHoverSample(null); }}
                onClick={() => { if (s) { setPicked(s); onHoverSample(s); } }}
              >
                {own ? '●' : s?.status === 'occluded' ? '×' : spatial && s ? (spatialBinLabel(s) || '') : (s?.body_optical && s.body_optical > 0 ? '◦' : '')}
              </button>
            );
          })}
        </div>
        <div className="fpv-fov-note">
          {spatial
            ? `120° FOV · ${spatialMode} A0…A4 angular bins${spatialMode === 'OCCLUSION' || spatialMode === 'TEMPORAL_SPATIAL' ? ' · nearest-in-sector occlusion' : ''}`
            : '120° FOV · LEGACY LEFT|FORWARD|RIGHT'}
        </div>
      </div>
    </div>
  );
}
