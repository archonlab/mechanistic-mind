/** Presentation interest only — never changes Mechanistic Mind science. */
import type { InspectorId, WorkspaceId } from './stores';

export type InterestPlan = {
  preset: 'MINIMAL' | 'NORMAL' | 'FULL';
  products: string[];
  diagnostics: string[];
  analyzePolling: boolean;
  catalogPolling: boolean;
  pscShadow: 'never' | 'opt-in';
};

const INSPECT_PRODUCTS: Record<InspectorId, string[]> = {
  WORLD: [],
  WORLD_STATUS: [],
  BODY: [],
  SENSORS: ['cognition'],
  SIGNALS: ['signals', 'signal_sensorimotor'],
  COGNITION: ['cognition', 'smc', 'historical_sensorimotor_selection'],
  PREDICTIVE: ['psc', 'prediction', 'signal_sensorimotor', 'cognition'],
  MECHANISMS: [],
  EXPERIMENTER: ['experimenter'],
  EXPERIMENT: ['cognition', 'psc', 'prediction'],
  INTERVENTION: ['experimenter'],
  OBSERVE: ['cognition', 'prediction'],
  RUNS: [],
};

export function interestFor(workspace: WorkspaceId, inspector: InspectorId): InterestPlan {
  if (workspace === 'RUN') {
    return {
      preset: 'MINIMAL',
      products: [],
      diagnostics: [],
      analyzePolling: false,
      catalogPolling: false,
      pscShadow: 'never',
    };
  }
  if (workspace === 'ANALYZE') {
    return {
      preset: 'MINIMAL',
      products: [],
      diagnostics: [],
      analyzePolling: true,
      catalogPolling: false,
      pscShadow: 'never',
    };
  }
  return {
    preset: 'NORMAL',
    products: INSPECT_PRODUCTS[inspector] || [],
    diagnostics: inspector === 'SIGNALS' || inspector === 'PREDICTIVE'
      ? ['signal-sensorimotor']
      : [],
    analyzePolling: false,
    catalogPolling: inspector === 'MECHANISMS' || inspector === 'EXPERIMENT' || inspector === 'RUNS',
    pscShadow: inspector === 'PREDICTIVE' || inspector === 'SIGNALS' ? 'opt-in' : 'never',
  };
}

export async function applyObserverInterest(plan: InterestPlan): Promise<void> {
  try {
    await fetch('/api/observer/detail', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset: plan.preset }),
    });
    for (const product of plan.products) {
      await fetch('/api/observer/detail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product, enabled: true }),
      });
    }
  } catch {
    /* presentation interest is best-effort */
  }
}
