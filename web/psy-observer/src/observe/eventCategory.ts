/**
 * Observe V2 event classification — mechanism-aware.
 * Display / filter only; does not alter runtime events.
 */

export type ObserveEventClass =
  | 'MOTOR'
  | 'OSC'
  | 'LEGACY_FIELD'
  | 'VISION'
  | 'CONTACT'
  | 'BODY'
  | 'WORLD'
  | 'RESOURCE'
  | 'WORK'
  | 'COGNITION'
  | 'OTHER';

export type ObserveFilter =
  | 'ALL'
  | 'MOTOR'
  | 'OSC'
  | 'VISION'
  | 'CONTACT'
  | 'BODY'
  | 'WORLD'
  | 'SIGNAL';

/** SIGNAL sub-filter for mechanism routing. */
export type SignalMechanismFilter = 'ALL_SIGNALS' | 'OSCILLATORY' | 'LEGACY_FIELD';

export function observeEventClass(type: string): ObserveEventClass {
  const t = String(type || '').toUpperCase();
  if (
    t.includes('OSC_EMISSION')
    || t.includes('OSC_EMIT')
    || t.includes('OSCILLATORY')
    || t.includes('OSC_BAND')
    || t.includes('OSC_RECEPTION')
    || t.includes('OSC_PARAMETER')
  ) {
    return 'OSC';
  }
  if (
    t.includes('PHYSICAL_SIGNAL')
    || t.includes('FIELD_A')
    || t.includes('FIELD_B')
    || (t.includes('FIELD_') && !t.includes('OSC'))
  ) {
    return 'LEGACY_FIELD';
  }
  if (t.includes('SIGNAL') && !t.includes('OSC')) return 'LEGACY_FIELD';
  if (t.includes('VISION') || t.includes('OPTICAL') || t.includes('EXO_')) return 'VISION';
  if (t.includes('CONTACT') || t.includes('PUSH') || t.includes('COLLISION')) return 'CONTACT';
  if (
    t.includes('MOTOR')
    || t.includes('ACTION')
    || t.includes('DISCRETE')
    || t.includes('SCENARIO_SELECTED')
    || t.includes('NECK')
    || t.includes('LOCOMOTION')
  ) {
    return 'MOTOR';
  }
  if (t.includes('WORLD_INTERVENTION') || t.includes('ECOLOGY') || t.startsWith('WORLD_')) return 'WORLD';
  if (t.startsWith('BODY_') || t.startsWith('SITE_')) return 'BODY';
  if (t.includes('RESOURCE') || t.includes('COMPLEMENTARY')) return 'RESOURCE';
  if (t.includes('DEFORM') || t.includes('WORK')) return 'WORK';
  if (t.includes('PREDICTION') || t.includes('OBSERVATION') || t.includes('MEMORY')) return 'COGNITION';
  return 'OTHER';
}

/** Legacy App EVENT_FILTERS mapping (SIGNAL = OSC ∪ LEGACY_FIELD). */
export function eventCategory(type: string): string {
  const c = observeEventClass(type);
  if (c === 'OSC' || c === 'LEGACY_FIELD') return 'SIGNAL';
  if (c === 'MOTOR') return 'ACTION';
  if (c === 'VISION' || c === 'CONTACT') return 'BODY';
  if (c === 'WORLD') return 'MATERIAL';
  return c;
}

export function matchesObserveFilter(type: string, filter: ObserveFilter): boolean {
  if (filter === 'ALL') return true;
  const c = observeEventClass(type);
  if (filter === 'SIGNAL') return c === 'OSC' || c === 'LEGACY_FIELD';
  if (filter === 'MOTOR') return c === 'MOTOR';
  if (filter === 'OSC') return c === 'OSC';
  if (filter === 'VISION') return c === 'VISION';
  if (filter === 'CONTACT') return c === 'CONTACT';
  if (filter === 'BODY') return c === 'BODY' || c === 'VISION' || c === 'CONTACT';
  if (filter === 'WORLD') return c === 'WORLD';
  return true;
}

export function matchesSignalMechanismFilter(
  type: string,
  filter: SignalMechanismFilter,
): boolean {
  const c = observeEventClass(type);
  if (filter === 'ALL_SIGNALS') return c === 'OSC' || c === 'LEGACY_FIELD';
  if (filter === 'OSCILLATORY') return c === 'OSC';
  if (filter === 'LEGACY_FIELD') return c === 'LEGACY_FIELD';
  return false;
}

/** Banned semantic communication labels for Observe UI text. */
export const OBSERVE_BANNED_SEMANTIC_TERMS = [
  'communication',
  'language',
  'meaning',
  'word',
  'sentence',
  'question',
  'answer',
  'conversation',
  'intentional signaling',
  'attention',
  'recognition',
  'listening',
  'looking intentionally',
  'multitasking',
  'automatic skill',
  'talking',
  'listened',
  'looked_at',
  'called',
  'answered',
  'recognized',
  'followed',
  'greeted',
] as const;

export function containsBannedSemanticTerm(text: string): boolean {
  const lower = String(text || '').toLowerCase();
  return OBSERVE_BANNED_SEMANTIC_TERMS.some((t) => lower.includes(t));
}
