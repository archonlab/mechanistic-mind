/** S7C Destination-depth — Simulation Info owns center (active status, not setup). */

import { PhenomenonDetails } from '../components/PhenomenonDetails';
import { SettingInfoHelp } from '../components/SettingInfoHelp';
import type { ReactNode } from 'react';

type Props = {
  frame: any;
  status: any;
  pendingDraft?: boolean;
  selectedCell?: any;
  measurementSlot?: ReactNode;
};

export function SimulationInfoWorkspace({
  frame,
  status,
  pendingDraft = false,
  selectedCell,
  measurementSlot,
}: Props) {
  const header = frame?.header || {};
  const experiment = frame?.experiment || {};
  const runtime = experiment.runtime || {};
  const tick = status?.simTick ?? status?.tick ?? header.tick ?? '—';
  const gen = status?.runtimeGeneration ?? header.runtime_generation ?? '—';
  const preset = header.public_preset || runtime.public_preset || '—';
  const seed = experiment.seed ?? header.seed ?? '—';
  const w = runtime.width ?? experiment.width ?? '—';
  const h = runtime.height ?? experiment.height ?? '—';
  const agents = runtime.agent_count ?? frame?.agents_observer?.length ?? '—';
  const psc = frame?.physical?.prospective_scenario_competition
    || experiment?.mechanisms?.prospective_scenario_competition;
  const pscState = psc?.enabled === true || psc === true ? 'ON' : (psc?.enabled === false || psc === false ? 'OFF' : '—');
  const pscSched = runtime.psc_schedule || {};
  const pscArmed = Boolean(pscSched.armed) || (pscState === 'OFF' && pscSched.schedule != null && pscSched.schedule !== 'MANUAL');
  const pscLabel = pscSched.activated_tick != null
    ? `ON · enabled@${pscSched.activated_tick}`
    : (pscArmed ? `OFF · scheduled@${pscSched.schedule}` : pscState);

  const categories = [
    {
      id: 'measurements',
      title: 'World measurements',
      summary: selectedCell ? 'selection present' : 'select a cell/object in a compatible viewport',
      children: (
        <div className="subtle">
          {selectedCell ? (
            measurementSlot || <pre className="phenomenon-pre">{JSON.stringify(selectedCell, null, 2).slice(0, 1500)}</pre>
          ) : (
            <p data-testid="siminfo-empty-selection">
              Select a cell, surface, object or organism in a compatible viewport to inspect it.
            </p>
          )}
        </div>
      ),
    },
    {
      id: 'cell',
      title: 'Selected cell/facet/object inspector',
      summary: selectedCell ? 'open below' : 'no selection',
      children: (
        <div className="subtle">
          {selectedCell
            ? <div>Selection payload available — see World measurements category for compact view.</div>
            : <div>No selection. World Map / Volume / Surface provide selection affordances.</div>}
        </div>
      ),
    },
    {
      id: 'mechanisms',
      title: 'Runtime mechanisms',
      summary: 'status snapshot — not Model setup inventory',
      children: (
        <div className="subtle">
          Mechanism ON/OFF inventory lives in Scientific Tools → Experiment / Ablations (draft) and Authorities.
          Simulation Info does not duplicate the full registry as primary content.
        </div>
      ),
    },
    {
      id: 'active_config',
      title: 'Active configuration',
      summary: pendingDraft ? 'draft differs from active' : 'draft matches active (or unknown)',
      children: (
        <div className="subtle">
          <div>active public_preset = {String(preset)}</div>
          <div>draft pending = {String(pendingDraft)}</div>
          <div>World/Model setup edits the shared draft — Apply is Review-only.</div>
        </div>
      ),
    },
    {
      id: 'history',
      title: 'Config history and interventions',
      summary: 'open Intervention / Authorities tools for receipts',
      children: (
        <div className="subtle">
          Live interventions and config history remain on Scientific Tools → Intervention / Authorities.
        </div>
      ),
    },
    {
      id: 'perf',
      title: 'Performance/health',
      summary: String(status?.executionMode || header.execution_mode || '—'),
      children: (
        <div className="subtle">
          <div>execution_mode = {String(status?.executionMode || header.execution_mode || '—')}</div>
          <div>status = {String(status?.status || header.status || '—')}</div>
          <div>evidence_mode = {String(status?.evidenceMode || header.evidence_mode || '—')}</div>
        </div>
      ),
    },
    {
      id: 'evidence',
      title: 'Evidence/capture status',
      summary: 'live ≠ saved packages',
      children: (
        <div className="subtle">
          Live runtime is not a saved evidence package. Use Scientific Tools → Saved Runs / Analyzer for packages.
        </div>
      ),
    },
    {
      id: 'authority',
      title: 'Authority/fingerprints',
      summary: 'schemas and digests last',
      children: (
        <div className="subtle">
          <div>runtime_generation = {String(gen)}</div>
          <div>model_line = {String(header.model_line || runtime.model_line || '—')}</div>
          <div>schema = {String(header.schema || frame?.schema || '—')}</div>
          <div>Unsupported values are omitted — never fabricated.</div>
        </div>
      ),
    },
  ];

  return (
    <div
      className="siminfo-central-workspace"
      data-testid="simulation-info-workspace"
      data-owns-center="true"
      aria-label="Simulation information"
    >
      <header className="fpv-central-header">
        <strong>SIMULATION INFO</strong>
        <span className="subtle">Active simulation status · not World/Model setup</span>
        <SettingInfoHelp
          label="Simulation Info"
          brief="Inspect the active run. Configuration belongs on World/Model with Review/Apply. resource-* entities are DEVELOPMENT_FIXTURE objects, not canonical food/goals."
          detail={(
            <div>
              <p>
                resource-* entities and associated resource mechanisms are temporary development fixtures
                used to exercise physical contact, sensorimotor consequence, material transfer, work
                accounting, and ecology mechanisms. They are not a canonical ontology of the Mechanistic
                Mind world.
              </p>
              <p>
                Physical effects remain part of this run. Replacement belongs to future Ecology +
                spherical-world + Causality Generator work and requires a new public-model fingerprint.
              </p>
            </div>
          )}
          testId="info-simulation-info"
        />
      </header>

      <div className="siminfo-primary panel" data-testid="simulation-info-primary">
        <div className="organism-state-grid">
          <div><span className="subtle">Public model</span><strong>{String(preset)}</strong></div>
          <div><span className="subtle">Tick</span><strong>{String(tick)}</strong></div>
          <div><span className="subtle">Generation</span><strong>{String(gen)}</strong></div>
          <div><span className="subtle">State</span><strong>{String(status?.status || header.status || '—')}</strong></div>
          <div><span className="subtle">Seed</span><strong>{String(seed)}</strong></div>
          <div><span className="subtle">World size</span><strong>{String(w)}×{String(h)}</strong></div>
          <div><span className="subtle">Agents</span><strong>{String(agents)}</strong></div>
          <div data-testid="siminfo-psc"><span className="subtle">PSC</span><strong>{String(pscLabel)}</strong></div>
          <div><span className="subtle">Evidence</span><strong>{String(status?.evidenceMode || '—')}</strong></div>
          <div><span className="subtle">Draft</span><strong>{pendingDraft ? 'UNAPPLIED' : 'MATCHED / —'}</strong></div>
          <div data-testid="siminfo-package-identity">
            <span className="subtle">Package</span>
            <strong>{String(header.package_identity || status?.packageIdentity || '—')}</strong>
          </div>
          <div data-testid="beta4-scientific-status">
            <span className="subtle">Scientific status</span>
            <strong>Beta 4: partially validated — bounded supported claims</strong>
          </div>
        </div>
      </div>
      <details className="phenomenon-category" data-testid="scientific-provenance-panel">
        <summary className="phenomenon-category-summary">
          <span className="phenomenon-category-title">Scientific provenance</span>
          <span className="phenomenon-category-line subtle">Collapsed · post-V1B authority</span>
        </summary>
        <div className="subtle phenomenon-category-body">
          <div>Current generation: GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR</div>
          <div>Provenance: Post-V1B repaired-physics scientific generation</div>
          <div>Claim matrix: results/acanthostega_beta4_s6_post_v1b_scientific_behavioral_closure/</div>
          <div>Pre-V1B S6 packages are historical/superseded — not current authority.</div>
        </div>
      </details>

      <PhenomenonDetails categories={categories} testIdPrefix="siminfo" />
    </div>
  );
}
