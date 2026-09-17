import type { AnalysisState } from './aggregates.ts';
import type { InteractionSummary } from './types.ts';

export function buildInteractions(
  state: AnalysisState,
  episodes: Array<{ start: number; end: number; ticks: number }>,
): InteractionSummary {
  const contactEmissions = Object.values(state.agents).reduce((s, a) => s + a.emit_contact, 0);
  const cross = Object.values(state.agents).reduce((s, a) => s + a.cross_agent_contrib, 0);
  const snippets: InteractionSummary['causal_snippets'] = [];
  if (state.first_contact_tick != null) {
    snippets.push({
      tick: state.first_contact_tick,
      steps: [
        `body-0 × body-1 soft contact (tick ${state.first_contact_tick})`,
        'FIELD_B deposits from contacting bodies (when signal emission enabled)',
        'local FIELD_B elevated → PHYSICAL_SIGNAL_RECEIVED (mixed / not uniquely attributable)',
      ],
      evidence_class: 'CAUSALLY_LINKED',
    });
  }
  for (const p of state.causal_pairs.slice(0, 8)) {
    if (p.meta?.emitter && p.meta?.receiver && p.meta.emitter !== p.meta.receiver) {
      snippets.push({
        tick: p.tick,
        steps: [
          `emission ${p.parent} from ${p.meta.emitter}`,
          'shared-world field superposition',
          `reception by ${p.meta.receiver} lists emission as same-tick contributing parent (${p.meta.attribution || 'attribution recorded'})`,
        ],
        evidence_class: 'CAUSALLY_LINKED',
      });
    }
  }
  const notes: string[] = [
    'Physical signal coupling is not communication.',
    'Contact mechanics are soft body-body overlap; not combat.',
  ];
  if (state.first_contact_tick == null) notes.push('No body-body contact observed in ingested timeline.');
  return {
    first_contact_tick: state.first_contact_tick,
    contact_ticks: state.contact_ticks,
    contact_episodes: episodes.slice(-40),
    contact_triggered_emissions: contactEmissions,
    cross_agent_contributions: cross,
    causal_snippets: snippets.slice(0, 12),
    notes,
  };
}
