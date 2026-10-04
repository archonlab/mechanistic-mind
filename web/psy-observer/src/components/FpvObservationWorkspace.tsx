/** S7C Phase B — FPV owns the central observation workspace.

Reuses exact O4 OrganismReceptorGroundedFpvPanel. Display-only.
No Apply, no tick reset, no second perception implementation.
*/

import { useMemo, useState } from 'react';
import { useFrameStore } from '../observer/useExternalStore';
import {
  OrganismReceptorGroundedFpvPanel,
  type FpvSubMode,
} from './OrganismReceptorGroundedFpvPanel';
import { PhenomenonDetails, type PhenomenonCategory } from './PhenomenonDetails';

export type FpvCentralMode = 'RECEPTOR_FPV' | 'COGNITION_FPV' | 'CAUSAL_SPLIT';

type Props = {
  selectedAgentId: string;
  agentCount: number;
  onSelectAgent: (index: number) => void;
};

function liveState(latest: any, available: boolean): 'LIVE' | 'ZERO' | 'UNAVAILABLE' {
  if (!available) return 'UNAVAILABLE';
  if (latest?.true_zero_exact_trace) return 'ZERO';
  return 'LIVE';
}

export function FpvObservationWorkspace({
  selectedAgentId,
  agentCount,
  onSelectAgent,
}: Props) {
  const frame = useFrameStore();
  const world = frame?.world || {};
  const view = world.organism_receptor_grounded_3d_fpv;
  const latest = view?.latest;
  const available = Boolean(view?.available && latest);
  const missing = view?.missing_reason || (!view ? 'NO_PAYLOAD' : null);
  const header = frame?.header || {};
  const [mode, setMode] = useState<FpvCentralMode>('RECEPTOR_FPV');

  const state = liveState(latest, available);
  const contribs = Array.isArray(latest?.accepted_contributions) ? latest.accepted_contributions : [];
  const cognBins = Array.isArray(latest?.cognition_fpv_bins) ? latest.cognition_fpv_bins : [];
  const n = Math.max(1, agentCount);

  const categories: PhenomenonCategory[] = useMemo(() => {
    const accepted = latest?.accepted_count ?? contribs.length;
    const rejected = latest?.rejected_count ?? latest?.rejected_excluded_count ?? '—';
    const occluded = latest?.occluded_count ?? '—';
    return [
      {
        id: 'reached',
        title: 'What reached the receptors',
        summary: available
          ? `accepted=${accepted} · true_zero=${Boolean(latest?.true_zero_exact_trace)}`
          : `UNAVAILABLE · ${String(missing)}`,
        children: (
          <div className="subtle">
            <div>accepted_count = {String(accepted)}</div>
            <div>receptor_tick = {String(latest?.receptor_tick ?? '—')}</div>
            <div>bands = {String(latest?.band_count ?? view?.band_count ?? '6 anonymous optical bands')}</div>
            <div>true_zero_exact_trace = {String(Boolean(latest?.true_zero_exact_trace))}</div>
            <div>Missing ≠ darkness. True zero is a valid exact O4 frame.</div>
          </div>
        ),
      },
      {
        id: 'spatial',
        title: 'Spatial and depth reconstruction',
        summary: available
          ? `contribs=${contribs.length} · exact distance_3d`
          : 'no spatial samples',
        children: (
          <div className="subtle">
            {contribs.length === 0 ? (
              <div>No accepted contributions in this frame.</div>
            ) : (
              <ul className="phenomenon-compact-list">
                {contribs.slice(0, 12).map((c: any, i: number) => (
                  <li key={String(c?.contribution_id || i)}>
                    az={Number(c?.azimuth_deg).toFixed(1)}° · el={Number(c?.elevation_deg).toFixed(1)}° ·
                    d3d={Number(c?.distance_3d).toFixed(3)}
                  </li>
                ))}
              </ul>
            )}
            <div>Projection uses exact O4 azimuth / elevation / distance_3d — no frontend raycast.</div>
          </div>
        ),
      },
      {
        id: 'spectral',
        title: 'Spectral contributions',
        summary: `${view?.display_band_transform || latest?.display_band_transform || 'pair-fold'} · NONPHYSICAL display RGB`,
        children: (
          <div className="subtle">
            <div>Six anonymous optical bands · pair-fold display transform.</div>
            <div>Display RGB is explicitly <strong>NONPHYSICAL</strong> — not human RGB, not camera imagery.</div>
            <div>transform = {String(view?.display_band_transform || latest?.display_band_transform || '—')}</div>
          </div>
        ),
      },
      {
        id: 'occlusion',
        title: 'Occlusion and rejected candidates',
        summary: `accepted=${accepted} · occluded=${String(occluded)} · rejected=${String(rejected)}`,
        children: (
          <div className="subtle">
            <div>Rejected / occluded contributions are excluded from Receptor FPV.</div>
            <div>accepted={String(accepted)} · occluded={String(occluded)} · rejected={String(rejected)}</div>
            <div>Researcher-only LOS rays (if enabled elsewhere) do not enter cognition.</div>
          </div>
        ),
      },
      {
        id: 'cognition',
        title: 'Cognition boundary',
        summary: `exo_bins=${cognBins.length} · discarded detail not restored`,
        children: (
          <div className="subtle">
            <div>Cognition FPV shows only phenotype / clip / fold survivors.</div>
            <div>Switching Receptor ↔ Cognition is display-only — no Apply, no new trace.</div>
            <div>bins={cognBins.length}</div>
          </div>
        ),
      },
      {
        id: 'timing',
        title: 'Timing and O5 alignment',
        summary: available
          ? `obs=${latest?.observation_tick ?? '—'} · receptor=${latest?.receptor_tick ?? '—'} · gen=${latest?.runtime_generation ?? '—'}`
          : 'timing unavailable',
        children: (
          <div className="subtle">
            <div>physical/receptor/observation ticks from exact O4/O5 payload.</div>
            <div>observation_tick = {String(latest?.observation_tick ?? '—')}</div>
            <div>receptor_tick = {String(latest?.receptor_tick ?? '—')}</div>
            <div>visual_causal_delay = {String(latest?.visual_causal_delay ?? latest?.causal_delay ?? '—')}</div>
            <div>runtime_generation = {String(latest?.runtime_generation ?? header.runtime_generation ?? '—')}</div>
            <div>frame/trace = {String(latest?.trace_id || '—')}</div>
          </div>
        ),
      },
      {
        id: 'authority',
        title: 'Scientific authority and limitations',
        summary: `${view?.schema || 'O4'} · not a camera · not human RGB · not conscious experience`,
        children: (
          <div className="subtle">
            <div>schema = {String(view?.schema || '—')}</div>
            <div>capability = {String(view?.capability || '—')}</div>
            <div>profile = {String(view?.profile || '—')}</div>
            <div>authority = {String(view?.authority || view?.classification || '—')}</div>
            <div>trace_id = {String(latest?.trace_id || '—')}</div>
            <div>digest = {String(latest?.digest || view?.digest || '—')}</div>
            <div><strong>NOT A CAMERA</strong> · <strong>NOT HUMAN RGB</strong> · <strong>NOT CONSCIOUS EXPERIENCE</strong></div>
            <div>No VW7 pixels · no frontend raycast · no physical-light recomputation in frontend.</div>
            <div>Researcher pixels never enter cognition. Saved-run / legacy gaps remain UNAVAILABLE.</div>
          </div>
        ),
      },
    ];
  }, [view, latest, available, missing, contribs, cognBins, header.runtime_generation]);

  const initialMode: FpvSubMode = mode === 'COGNITION_FPV' ? 'COGNITION_FPV' : 'RECEPTOR_FPV';

  return (
    <div
      className="fpv-central-workspace"
      data-testid="fpv-central-workspace"
      data-mode={mode}
      data-live-state={state}
      data-owns-center="true"
    >
      <header className="fpv-central-header" data-testid="fpv-central-header">
        <div className="fpv-central-agents" role="group" aria-label="Selected organism">
          {Array.from({ length: n }, (_, i) => (
            <button
              key={i}
              type="button"
              className={selectedAgentId === `agent_${i}` ? 'active' : ''}
              data-testid={`fpv-select-agent-${i}`}
              onClick={() => onSelectAgent(i)}
            >
              AGENT {i}
            </button>
          ))}
        </div>
        <div className="fpv-central-modes" role="group" aria-label="FPV display mode">
          {(
            [
              ['RECEPTOR_FPV', 'RECEPTOR FPV'],
              ['COGNITION_FPV', 'COGNITION FPV'],
              ['CAUSAL_SPLIT', 'CAUSAL SPLIT'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={mode === id ? 'active' : ''}
              data-testid={`fpv-central-mode-${id.toLowerCase()}`}
              onClick={() => setMode(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="fpv-central-status" data-testid="fpv-central-status">
          <span data-testid="fpv-live-state" data-state={state}>{state}</span>
          <span className="subtle">
            obs={String(latest?.observation_tick ?? '—')} · receptor={String(latest?.receptor_tick ?? '—')} ·
            tick={String(header.tick ?? '—')} · gen={String(header.runtime_generation ?? '—')}
          </span>
        </div>
      </header>

      <div className="fpv-central-primary" data-testid="fpv-central-primary">
        {mode === 'CAUSAL_SPLIT' ? (
          <div className="fpv-causal-split" data-testid="fpv-causal-split">
            <div className="fpv-split-pane">
              <div className="section-label">RECEPTOR (before cognition fold)</div>
              <OrganismReceptorGroundedFpvPanel
                agentFilter={selectedAgentId}
                initialMode="RECEPTOR_FPV"
                chrome="primary"
                fillParent
              />
            </div>
            <div className="fpv-split-pane">
              <div className="section-label">COGNITION (surviving fold only)</div>
              <OrganismReceptorGroundedFpvPanel
                agentFilter={selectedAgentId}
                initialMode="COGNITION_FPV"
                chrome="primary"
                fillParent
              />
            </div>
            <p className="subtle fpv-split-note">
              Researcher boundary view — the organism does not see this split visualization.
            </p>
          </div>
        ) : (
          <OrganismReceptorGroundedFpvPanel
            agentFilter={selectedAgentId}
            initialMode={initialMode}
            chrome="primary"
            fillParent
          />
        )}
      </div>

      <PhenomenonDetails categories={categories} testIdPrefix="fpv" />
    </div>
  );
}
