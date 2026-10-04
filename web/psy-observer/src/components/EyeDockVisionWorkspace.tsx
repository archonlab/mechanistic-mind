/** S7D — Eye dock dual-agent FPV comparison (researcher display only).

Uses exact existing O4 latest_exact_by_agent traces. No second perception,
no raycast, no VW7 pixels, no selected-agent mutation on passive updates.
Hearing/tab switches must not destroy retained per-agent exact traces.
*/

import { useMemo, useRef, useState } from 'react';
import { useFrameStore } from '../observer/useExternalStore';
import {
  OrganismReceptorGroundedFpvPanel,
  type FpvSubMode,
} from './OrganismReceptorGroundedFpvPanel';
import { PhenomenonDetails, type PhenomenonCategory } from './PhenomenonDetails';
import { SettingInfoHelp } from './SettingInfoHelp';
import {
  absorbLatestExactByAgent,
  liveState,
  traceForAgent,
  type ExactTraceLike,
} from './eyeDockDualFpvLifecycle';

const MAX_VISIBLE_CARDS = 2;

function agentIdsFromFrame(frame: any, agentCount: number, retainedKeys: string[] = []): string[] {
  const view = frame?.world?.organism_receptor_grounded_3d_fpv;
  const fromMap = view?.latest_exact_by_agent && typeof view.latest_exact_by_agent === 'object'
    ? Object.keys(view.latest_exact_by_agent)
    : [];
  const fromKeys = Array.isArray(view?.agents_with_latest) ? view.agents_with_latest.map(String) : [];
  const fromObservers = Array.isArray(frame?.agents_observer)
    ? frame.agents_observer.map((_: any, i: number) => `agent_${i}`)
    : [];
  const n = Math.max(0, Number(agentCount) || 0);
  const synthetic = Array.from({ length: n }, (_, i) => `agent_${i}`);
  const merged = [...new Set([...synthetic, ...fromKeys, ...fromMap, ...retainedKeys, ...fromObservers].map(String))];
  if (n > 0) return merged.filter((id) => {
    const m = /^agent_(\d+)$/.exec(id);
    return m ? Number(m[1]) < n : true;
  }).sort();
  return merged.sort();
}

export function EyeDockVisionWorkspace({
  dockWide = false,
  hidden = false,
  agentCount = 2,
  selectedAgentId,
  onSelectAgent,
  onOpenDetailedFpv,
  onEditVisionConfig,
}: {
  dockWide?: boolean;
  hidden?: boolean;
  agentCount?: number;
  selectedAgentId: string;
  onSelectAgent?: (index: number) => void;
  onOpenDetailedFpv?: (index: number) => void;
  onEditVisionConfig?: () => void;
}) {
  const frame = useFrameStore();
  const view = frame?.world?.organism_receptor_grounded_3d_fpv;
  const retainedExactByAgentRef = useRef<Record<string, ExactTraceLike>>({});
  // Absorb fresh dual-map entries; do not clear on omission (Hearing / closed paint).
  absorbLatestExactByAgent(retainedExactByAgentRef.current, view?.latest_exact_by_agent);
  const retainedExactByAgent = retainedExactByAgentRef.current;
  const [dockMode, setDockMode] = useState<FpvSubMode>('RECEPTOR_FPV');
  const [smooth, setSmooth] = useState(false);
  const [page, setPage] = useState(0);

  const allIds = useMemo(
    () => agentIdsFromFrame(frame, agentCount, Object.keys(retainedExactByAgent)),
    [frame, agentCount, retainedExactByAgent, view?.latest_exact_by_agent_included],
  );
  const pageCount = Math.max(1, Math.ceil(Math.max(allIds.length, 1) / MAX_VISIBLE_CARDS));
  const safePage = Math.min(page, pageCount - 1);
  const visibleIds = allIds.slice(safePage * MAX_VISIBLE_CARDS, safePage * MAX_VISIBLE_CARDS + MAX_VISIBLE_CARDS);

  const categories: PhenomenonCategory[] = useMemo(() => {
    const rows = allIds.map((id) => {
      const tr = traceForAgent(view, id, retainedExactByAgent);
      return { id, tr, state: liveState(tr) };
    });
    const pair = (pick: (r: { id: string; tr: any }) => string) =>
      rows.map((r) => `${r.id}=${pick(r)}`).join(' · ') || '—';

    return [
      {
        id: 'receptor',
        title: 'RECEPTOR SUMMARY',
        summary: pair((r) => (r.tr ? `accepted=${r.tr.accepted_count ?? (r.tr.accepted_contributions?.length ?? 0)}` : 'UNAVAILABLE')),
        children: (
          <div className="subtle eye-dual-compare">
            {rows.map((r) => (
              <div key={r.id} data-testid={`eye-dual-receptor-${r.id}`}>
                <strong>{r.id}</strong>: {r.tr
                  ? `accepted=${r.tr.accepted_count ?? '—'} · true_zero=${Boolean(r.tr.true_zero_exact_trace)} · obs=${r.tr.observation_tick ?? '—'} · receptor=${r.tr.receptor_tick ?? '—'}`
                  : 'UNAVAILABLE'}
              </div>
            ))}
          </div>
        ),
      },
      {
        id: 'spatial',
        title: 'SPATIAL AND DEPTH',
        summary: pair((r) => (r.tr ? `contribs=${Array.isArray(r.tr.accepted_contributions) ? r.tr.accepted_contributions.length : 0}` : 'missing')),
        children: (
          <div className="subtle">Exact distance_3d from O4 contributions only. No frontend raycast.</div>
        ),
      },
      {
        id: 'spectral',
        title: 'SPECTRAL CONTRIBUTIONS',
        summary: 'anonymous optical bands · display RGB nonphysical',
        children: (
          <div className="subtle">
            {rows.map((r) => (
              <div key={r.id}>{r.id}: bands={String(r.tr?.band_count ?? view?.band_count ?? '—')}</div>
            ))}
          </div>
        ),
      },
      {
        id: 'occlusion',
        title: 'OCCLUSION AND REJECTED CANDIDATES',
        summary: pair((r) => (r.tr ? `rejected=${r.tr.rejected_count ?? r.tr.rejected_excluded_count ?? '—'}` : '—')),
        children: (
          <div className="subtle">Rejected/occluded candidates are audit-only; not restored into FPV blobs.</div>
        ),
      },
      {
        id: 'cognition',
        title: 'COGNITION BOUNDARY',
        summary: pair((r) => (r.tr ? `bins=${Array.isArray(r.tr.cognition_fpv_bins) ? r.tr.cognition_fpv_bins.length : 0}` : '—')),
        children: (
          <div className="subtle">Cognition FPV shows phenotype/clip survivors only — cannot restore discarded receptor detail.</div>
        ),
      },
      {
        id: 'o5',
        title: 'O5 TIMING',
        summary: pair((r) => (r.tr ? `obs=${r.tr.observation_tick ?? '—'} rec=${r.tr.receptor_tick ?? '—'}` : '—')),
        children: (
          <div className="subtle">Observation tick and receptor tick are exact trace fields. Dock display does not invent timing.</div>
        ),
      },
      {
        id: 'authority',
        title: 'AUTHORITY AND LIMITATIONS',
        summary: `${view?.schema || '—'} · dual_map=${Boolean(view?.latest_exact_by_agent_included)}`,
        children: (
          <div className="subtle">
            <div>schema={String(view?.schema || '—')}</div>
            <div>profile={String(view?.profile || '—')}</div>
            <div>authority={String(view?.authority || '—')}</div>
            <div>classification={String(view?.classification || '—')}</div>
            <div>latest_exact_by_agent_included={String(Boolean(view?.latest_exact_by_agent_included))}</div>
            <div>display_band_transform={String(view?.display_band_transform || '—')} · NONPHYSICAL</div>
            <div>Not a camera · not human RGB · not conscious experience · VW7 pixels unused</div>
            {rows.map((r) => (
              <div key={r.id}>{r.id} trace_id={r.tr?.trace_id ? String(r.tr.trace_id).slice(0, 12) : '—'}</div>
            ))}
          </div>
        ),
      },
    ];
  }, [allIds, view, retainedExactByAgent]);

  if (allIds.length === 0) {
    return (
      <div className="eye-dual-fpv" data-testid="eye-dual-fpv" data-agent-count="0">
        <div className="subtle" role="status">No active agents — dual FPV unavailable.</div>
      </div>
    );
  }

  return (
    <div
      className={`eye-dual-fpv ${dockWide ? 'wide' : 'normal'}`}
      data-testid="eye-dual-fpv"
      data-agent-count={String(allIds.length)}
      data-dock-mode={dockMode}
      data-wide={String(dockWide)}
    >
      <div className="eye-dual-fpv-head">
        <strong>DUAL FPV</strong>
        <span className="subtle">simultaneous O4 · researcher comparison</span>
        <SettingInfoHelp
          label="Dual FPV"
          brief="Exact O4 latest traces for active agents. Display only."
          detail="Passive updates never change selected agent. Card click selects for detailed inspection. Not a second perception engine."
          testId="eye-dual-fpv-help"
        />
      </div>

      {allIds.length > MAX_VISIBLE_CARDS ? (
        <div className="eye-dock-toolbar" data-testid="eye-dual-fpv-pager">
          <button type="button" disabled={safePage <= 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>PREV</button>
          <span className="subtle">agents {safePage * MAX_VISIBLE_CARDS + 1}–{Math.min(allIds.length, (safePage + 1) * MAX_VISIBLE_CARDS)} / {allIds.length}</span>
          <button type="button" disabled={safePage >= pageCount - 1} onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}>NEXT</button>
        </div>
      ) : null}

      <div className="eye-dual-fpv-grid" data-testid="eye-dual-fpv-grid" data-layout={dockWide && visibleIds.length > 1 ? 'side' : 'stack'}>
        {visibleIds.map((agentId) => {
          const tr = traceForAgent(view, agentId, retainedExactByAgent);
          const state = liveState(tr);
          const idx = Number((/^agent_(\d+)$/.exec(agentId) || [])[1] ?? 0);
          const isSelected = String(selectedAgentId) === String(agentId);
          return (
            <article
              key={agentId}
              className={`eye-dual-fpv-card ${isSelected ? 'selected' : ''}`}
              data-testid={`eye-dual-fpv-card-${agentId}`}
              data-agent={agentId}
              data-state={state}
              data-selected={String(isSelected)}
              data-trace-id={tr?.trace_id ? String(tr.trace_id) : ''}
              tabIndex={0}
              aria-label={`${agentId} FPV ${state}${isSelected ? ', selected' : ''}`}
              onClick={() => onSelectAgent?.(idx)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectAgent?.(idx);
                }
              }}
            >
              <header className="eye-dual-fpv-card-head">
                <strong>{agentId}</strong>
                <span className={`eye-dual-fpv-state state-${state.toLowerCase()}`} data-testid={`eye-dual-fpv-state-${agentId}`}>
                  {state}
                </span>
                {isSelected ? <span className="subtle">selected</span> : null}
              </header>
              <div className="subtle eye-dual-fpv-ticks">
                obs={tr?.observation_tick ?? '—'} · receptor={tr?.receptor_tick ?? '—'}
                {tr?.runtime_generation != null ? ` · gen=${tr.runtime_generation}` : ''}
              </div>
              <OrganismReceptorGroundedFpvPanel
                agentFilter={agentId}
                chrome="compact"
                externalTrace={tr}
                controlledMode={dockMode}
                displaySmooth={smooth}
                hidden={hidden}
              />
              <div className="eye-dual-fpv-card-actions">
                <button
                  type="button"
                  data-testid={`eye-dual-open-fpv-${agentId}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenDetailedFpv?.(idx);
                  }}
                >
                  Open detailed FPV
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <section className="eye-dual-fpv-settings" data-testid="eye-dual-fpv-settings" aria-label="Vision display settings">
        <div className="eye-dock-toolbar">
          <strong>DISPLAY</strong>
          <button
            type="button"
            className={dockMode === 'RECEPTOR_FPV' ? 'active' : ''}
            data-testid="eye-dual-mode-receptor"
            onClick={() => setDockMode('RECEPTOR_FPV')}
          >
            Receptor
          </button>
          <SettingInfoHelp
            label="Receptor versus Cognition"
            brief="Same dock mode applies to both cards for comparison."
            detail="Receptor = exact accepted O4 contributions. Cognition = phenotype/clip survivors only. Display-only; no reset; no new trace."
            testId="eye-dual-mode-help"
          />
          <button
            type="button"
            className={dockMode === 'COGNITION_FPV' ? 'active' : ''}
            data-testid="eye-dual-mode-cognition"
            onClick={() => setDockMode('COGNITION_FPV')}
          >
            Cognition
          </button>
          <label className="subtle">
            <input
              type="checkbox"
              data-testid="eye-dual-smooth"
              checked={smooth}
              onChange={(e) => setSmooth(e.target.checked)}
            />{' '}
            display smooth
          </label>
          <SettingInfoHelp
            label="Display smoothing"
            brief="Nonphysical blur for researcher readability."
            detail="Does not invent samples or change O4 contributions. Default OFF."
            testId="eye-dual-smooth-help"
          />
        </div>
        <div className="subtle">
          <button
            type="button"
            className="linkish"
            data-testid="eye-dual-edit-vision-config"
            onClick={() => onEditVisionConfig?.()}
          >
            Edit experiment vision configuration
          </button>
          <span> · draft only · no Apply here</span>
        </div>
      </section>

      <PhenomenonDetails categories={categories} testIdPrefix="eye-dual" />
    </div>
  );
}
