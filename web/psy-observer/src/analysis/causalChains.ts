import type { AnalysisState } from './aggregates.ts';
import { BOUNDS } from './aggregates.ts';
import type { CausalChain } from './types.ts';

/**
 * Reconstruct causal chains only from explicit emission_id / causal_parent_ids evidence.
 * Never promote temporal adjacency alone to causation.
 */
export function buildCausalChains(state: AnalysisState): CausalChain[] {
  const chains: CausalChain[] = [];
  for (const p of state.causal_pairs) {
    const nodes = [
      `emission:${p.parent}`,
      'field_superposition',
      `reception:${p.child}`,
    ];
    chains.push({
      id: `chain-${p.tick}-${p.parent}`,
      tick: p.tick,
      nodes,
      edges: [
        {
          from: `emission:${p.parent}`,
          to: 'field_superposition',
          link: 'DIRECT_CAUSAL_LINK',
          reason: 'Deposit into shared FIELD_* is the physical emission operation.',
        },
        {
          from: 'field_superposition',
          to: `reception:${p.child}`,
          link: 'DIRECT_CAUSAL_LINK',
          reason: 'Reception lists emission_id in contributing_emissions_this_tick / causal_parent_ids.',
        },
        {
          from: `reception:${p.child}`,
          to: 'later_cognition',
          link: 'NOT_ESTABLISHED',
          reason:
            'No explicit causal_parent link from reception to prediction/action. ' +
            'Cognition sees anonymous local.FIELD_* floats only (SIGINT-01).',
        },
      ],
    });
  }
  // Contact → emission firsts
  if (state.firsts.first_contact_emission && state.firsts.first_body_body_contact) {
    const t = state.firsts.first_contact_emission.tick;
    chains.unshift({
      id: `chain-contact-emission-${t}`,
      tick: t,
      nodes: ['body_body_contact', 'FIELD_B_deposit', 'PHYSICAL_SIGNAL_EMITTED'],
      edges: [
        {
          from: 'body_body_contact',
          to: 'FIELD_B_deposit',
          link: 'DIRECT_CAUSAL_LINK',
          reason: 'Runtime deposits FIELD_B when soft contact is active (trigger=body_contact).',
        },
        {
          from: 'FIELD_B_deposit',
          to: 'PHYSICAL_SIGNAL_EMITTED',
          link: 'DIRECT_CAUSAL_LINK',
          reason: 'Observer emission event records the deposit receipt.',
        },
      ],
    });
  }
  return chains.slice(0, BOUNDS.max_causal_chains);
}
