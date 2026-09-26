/** Tiktaalik Eye — SENSOR SPACE + FPV diagnostic of canonical optical samples. */

import { useEffect, useState } from 'react';
import { useFrameStore } from '../observer/useExternalStore';
import type { SectorCell } from './tiktaalikEyeModel';
import { fmtDelta, fmtRaw } from './tiktaalikEyeModel';
import { TiktaalikFpvField } from './TiktaalikFpvField';
import type { EyeLink, FpvSample } from './tiktaalikFpvModel';

type Rate = 'OFF' | 'SNAPSHOT' | '2FPS' | '5FPS' | 'PER_TICK';
type Layout = 'A0' | 'A1' | 'SPLIT';
type EyeTab = 'SENSOR_SPACE' | 'FPV';
type FpvMode = 'OPTICAL' | 'CONTRIBUTION';

const RATES: Rate[] = ['OFF', 'SNAPSHOT', '2FPS', '5FPS', 'PER_TICK'];
const LAYOUTS: { id: Layout; label: string }[] = [
  { id: 'A0', label: 'A0' },
  { id: 'A1', label: 'A1' },
  { id: 'SPLIT', label: 'SPLIT' },
];

function MagBar({ cell }: { cell: SectorCell | undefined }) {
  if (!cell || !cell.present) {
    return <div className="eye-bar eye-bar-absent" title="Channel absent (not zero)" />;
  }
  const v = Math.max(0, Math.min(1, Number(cell.raw || 0)));
  return (
    <div className={`eye-bar ${cell.saturated ? 'eye-bar-sat' : ''} ${v === 0 ? 'eye-bar-zero' : ''}`}>
      <div className="eye-bar-fill" style={{ width: `${v * 100}%` }} />
    </div>
  );
}

function SectorCol({
  label,
  cell,
  linked,
  onHover,
}: {
  label: 'LEFT' | 'FORWARD' | 'RIGHT';
  cell: SectorCell | undefined;
  linked?: boolean;
  onHover?: (sector: 'LEFT' | 'FORWARD' | 'RIGHT' | null) => void;
}) {
  return (
    <div
      className={`eye-sector ${linked ? 'linked' : ''}`}
      onMouseEnter={() => onHover?.(label)}
      onMouseLeave={() => onHover?.(null)}
    >
      <div className="eye-sector-h">{label}</div>
      <MagBar cell={cell} />
      <div className="eye-num">
        {fmtRaw(cell)}
        {cell?.saturated ? ' SAT' : ''}
      </div>
      <div className="eye-pe">{cell?.pe_bin ? `PE ${cell.pe_bin.label}` : 'PE —'}</div>
      <div className="eye-d">Δ {fmtDelta(cell)}</div>
    </div>
  );
}

function ChannelRow({
  name,
  row,
  channel,
  link,
  onLink,
}: {
  name: string;
  row: any;
  channel: 'exo' | 'c0' | 'c1' | 'c2';
  link: EyeLink;
  onLink: (l: EyeLink) => void;
}) {
  if (!row || row.present === false) {
    return (
      <div className="eye-row">
        <div className="eye-lab">{name}</div>
        <div className="eye-absent">ABSENT</div>
      </div>
    );
  }
  const hover = (sector: 'LEFT' | 'FORWARD' | 'RIGHT' | null) => {
    onLink(sector ? { sector, channel } : null);
  };
  return (
    <div className="eye-row">
      <div className="eye-lab">{name}</div>
      <SectorCol label="LEFT" cell={row.left} linked={link?.sector === 'LEFT'} onHover={hover} />
      <SectorCol label="FORWARD" cell={row.forward} linked={link?.sector === 'FORWARD'} onHover={hover} />
      <SectorCol label="RIGHT" cell={row.right} linked={link?.sector === 'RIGHT'} onHover={hover} />
    </div>
  );
}

function AgentScope({
  agentId,
  panel,
  link,
  onLink,
}: {
  agentId: string;
  panel: any;
  link: EyeLink;
  onLink: (l: EyeLink) => void;
}) {
  const acc = panel?.accessible || {};
  const cfg = panel?.sensor_configuration || {};
  const spatial = String(cfg.spatial_vision || 'LEGACY').toUpperCase() !== 'LEGACY';
  return (
    <div className="eye-scope" data-testid={`tiktaalik-eye-${agentId}`}>
      <div className="eye-title">{String(agentId).replace('_', ' ').toUpperCase()} — SENSOR SPACE</div>
      <div className="subtle">{panel?.honesty || 'Agent-accessible optical accumulators. Not a camera.'}</div>
      <div className="eye-meta">
        <span>SENSOR CONFIGURATION (not cognition)</span>
        <strong>R={cfg.radius ?? '—'}</strong>
        <strong>FOV {cfg.fov_deg ?? '—'}°</strong>
        <strong>HEADING {cfg.heading_source || '—'}</strong>
        <strong>SURFACE {cfg.surface_discrimination || '—'}</strong>
        <strong>MAPPING {cfg.optical_mapping || '—'}</strong>
        <strong>SPATIAL {cfg.spatial_vision || 'LEGACY'}</strong>
      </div>
      {cfg.radius === 1 ? (
        <div className="subtle">R=1: farther cells are outside the Moore candidate set.</div>
      ) : null}
      {spatial && acc.spatial_exo?.present ? (
        <div data-testid="spatial-bins">
          <div className="section-label">A0–A4 EXO</div>
          <div className="eye-spatial-row">
            {(acc.spatial_exo.bins || []).map((b: any) => (
              <div
                key={b.key}
                className={`eye-spatial-bin ${link?.channel === 'spatial' && link?.spatialIndex === Number(String(b.label || 'A0').slice(1)) ? 'linked' : ''}`}
                onMouseEnter={() => onLink({ sector: String(b.label || '').toUpperCase(), channel: 'spatial', spatialIndex: Number(String(b.label || 'A0').slice(1)) })}
                onMouseLeave={() => onLink(null)}
              >
                <div className="eye-sector-h">{String(b.label || '').toUpperCase()}</div>
                <MagBar cell={b} />
                <div className="eye-num">{fmtRaw(b)}</div>
                <div className="eye-d">Δ {fmtDelta(b)}</div>
              </div>
            ))}
          </div>
          {['spatial_surface_c0', 'spatial_surface_c1', 'spatial_surface_c2'].map((sk, i) =>
            acc[sk]?.present ? (
              <div key={sk}>
                <div className="section-label">A0–A4 C{i}</div>
                <div className="eye-spatial-row">
                  {(acc[sk].bins || []).map((b: any) => (
                    <div key={b.key} className="eye-spatial-bin">
                      <div className="eye-sector-h">{String(b.label || '').toUpperCase()}</div>
                      <MagBar cell={b} />
                      <div className="eye-num">{fmtRaw(b)}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null,
          )}
        </div>
      ) : null}
      {!spatial ? (
        <>
          <div className="eye-grid-head">
            <span />
            <span>LEFT</span>
            <span>FORWARD</span>
            <span>RIGHT</span>
          </div>
          <ChannelRow name="EXO" row={acc.exo} channel="exo" link={link} onLink={onLink} />
          <ChannelRow name="SURFACE C0" row={acc.surface_c0} channel="c0" link={link} onLink={onLink} />
          <ChannelRow name="SURFACE C1" row={acc.surface_c1} channel="c1" link={link} onLink={onLink} />
          <ChannelRow name="SURFACE C2" row={acc.surface_c2} channel="c2" link={link} onLink={onLink} />
        </>
      ) : (
        <>
          <div className="section-label">3-SECTOR ACCUMULATORS (still sampled · exo_0/1/2)</div>
          <div className="eye-grid-head">
            <span />
            <span>LEFT</span>
            <span>FORWARD</span>
            <span>RIGHT</span>
          </div>
          <ChannelRow name="EXO" row={acc.exo} channel="exo" link={link} onLink={onLink} />
        </>
      )}
      <div className="section-label">TEMPORAL CHANGE</div>
      <div className="subtle">Δ VALUE from previous Eye sample. Not depth / distance / optical flow.</div>
    </div>
  );
}

export function TiktaalikEyePanel({
  layout,
  onLayout,
  captureEnabled = true,
}: {
  layout: Layout;
  onLayout?: (l: Layout) => void;
  captureEnabled?: boolean;
}) {
  const frame = useFrameStore();
  const [rate, setRate] = useState<Rate>('OFF');
  const [tab, setTab] = useState<EyeTab>('SENSOR_SPACE');
  const [fpvMode, setFpvMode] = useState<FpvMode>('OPTICAL');
  const [link, setLink] = useState<EyeLink>(null);
  const eye = frame?.tiktaalik_eye;
  const agents = eye?.agents || {};
  const a0 = agents.agent_0;
  const a1 = agents.agent_1;

  useEffect(() => {
    if (!captureEnabled) {
      void fetch('/api/observer/tiktaalik-eye', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rate: 'OFF', fpv: false }),
      }).catch(() => undefined);
      return;
    }
    fetch('/api/observer/tiktaalik-eye')
      .then((r) => r.json())
      .then((j) => {
        const rr = String(j.rate || 'OFF').toUpperCase();
        if (RATES.includes(rr as Rate)) setRate(rr as Rate);
        if (j.fpv) setTab('FPV');
      })
      .catch(() => undefined);
    return () => {
      void fetch('/api/observer/tiktaalik-eye', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rate: 'OFF', fpv: false }),
      }).catch(() => undefined);
    };
  }, [captureEnabled]);

  async function postEye(next: { rate?: Rate; fpv?: boolean }) {
    if (!captureEnabled) return;
    await fetch('/api/observer/tiktaalik-eye', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(next),
    });
  }

  async function changeRate(next: Rate) {
    setRate(next);
    await postEye({ rate: next, fpv: tab === 'FPV' });
  }

  async function changeTab(next: EyeTab) {
    setTab(next);
    await postEye({ rate, fpv: next === 'FPV' });
  }

  const showA0 = layout === 'A0' || layout === 'SPLIT';
  const showA1 = layout === 'A1' || layout === 'SPLIT';
  const showFpvA0 = showA0;
  const showFpvA1 = showA1;

  function onHoverSample(s: FpvSample | null) {
    if (!s) {
      setLink(null);
      return;
    }
    const spatialOn = [a0, a1].some(
      (p) => String(p?.fpv?.spatial_vision || p?.sensor_configuration?.spatial_vision || 'LEGACY').toUpperCase() !== 'LEGACY',
    );
    if (spatialOn && s.spatial_sector_index != null) {
      setLink({
        sector: String(s.spatial_sector_label || `A${s.spatial_sector_index}`).toUpperCase(),
        channel: 'spatial',
        spatialIndex: Number(s.spatial_sector_index),
      });
      return;
    }
    if (!s.sector) {
      setLink(null);
      return;
    }
    setLink({ sector: s.sector as 'LEFT' | 'FORWARD' | 'RIGHT', channel: 'exo' });
  }

  return (
    <div className="tiktaalik-eye" data-testid="tiktaalik-eye">
      <div className="eye-dock-toolbar">
        <strong>TIKTAALIK EYE</strong>
        {LAYOUTS.map((l) => (
          <button
            key={l.id}
            type="button"
            className={layout === l.id ? 'active' : ''}
            onClick={() => onLayout?.(l.id)}
          >
            {l.label}
          </button>
        ))}
        <button type="button" className={tab === 'SENSOR_SPACE' ? 'active' : ''} onClick={() => void changeTab('SENSOR_SPACE')}>
          SENSOR SPACE
        </button>
        <button type="button" className={tab === 'FPV' ? 'active' : ''} onClick={() => void changeTab('FPV')}>
          FPV
        </button>
      </div>
      <div className="eye-dock-toolbar">
        <span>Preview</span>
        {RATES.map((r) => (
          <button key={r} type="button" className={rate === r ? 'active' : ''} disabled={!captureEnabled} onClick={() => void changeRate(r)}>
            {r === '2FPS' ? '2 FPS' : r === '5FPS' ? '5 FPS' : r}
          </button>
        ))}
      </div>
      {tab === 'FPV' ? (
        <div className="eye-dock-toolbar">
          <button type="button" className={fpvMode === 'OPTICAL' ? 'active' : ''} onClick={() => setFpvMode('OPTICAL')}>
            OPTICAL FIELD
          </button>
          <button type="button" className={fpvMode === 'CONTRIBUTION' ? 'active' : ''} onClick={() => setFpvMode('CONTRIBUTION')}>
            CONTRIBUTION
          </button>
        </div>
      ) : null}
      <div className="subtle eye-dock-note">
        FPV = diagnostic receipts. SENSOR SPACE = cognition-accessible values. Not a camera. WORLD stays center.
        Runtime vision configuration: Experiment → Vision.
      </div>
      {eye?.status === 'OFF' || rate === 'OFF' || !captureEnabled ? (
        <div className="subtle">Preview OFF — diagnostic capture not requested.</div>
      ) : null}
      {tab === 'SENSOR_SPACE' ? (
        <div className={`eye-scopes ${layout === 'SPLIT' ? 'vertical' : ''}`}>
          {showA0 ? <AgentScope agentId="agent_0" panel={a0} link={link} onLink={setLink} /> : null}
          {showA1 ? <AgentScope agentId="agent_1" panel={a1} link={link} onLink={setLink} /> : null}
        </div>
      ) : (
        <div className={`eye-scopes ${layout === 'SPLIT' ? 'vertical' : ''}`}>
          {showFpvA0 ? (
            <TiktaalikFpvField
              agentId="agent_0"
              fpv={a0?.fpv}
              mode={fpvMode}
              link={link}
              onHoverSample={onHoverSample}
            />
          ) : null}
          {showFpvA1 ? (
            <TiktaalikFpvField
              agentId="agent_1"
              fpv={a1?.fpv}
              mode={fpvMode}
              link={link}
              onHoverSample={onHoverSample}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

export function TiktaalikEyeLayoutControls({
  layout,
  onLayout,
}: {
  layout: Layout;
  onLayout: (l: Layout) => void;
}) {
  return (
    <div className="eye-dock-toolbar">
      {LAYOUTS.map((l) => (
        <button
          key={l.id}
          type="button"
          className={layout === l.id ? 'active' : ''}
          onClick={() => onLayout(l.id)}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export type { Layout as EyeLayout };
