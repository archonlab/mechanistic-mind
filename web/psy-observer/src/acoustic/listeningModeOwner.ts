/** MUTUALLY_EXCLUSIVE_LISTENING_MODES — only one audible owner at a time. */
export type ListeningModeOwner =
  | 'OFF'
  | 'PHYSICAL_FIELD_C1'
  | 'SELECTED_ORGANISM_SAV2'
  | 'OFFLINE_SAV4B';

type ReleaseFn = () => void;

let owner: ListeningModeOwner = 'OFF';
let releaseC1: ReleaseFn | null = null;
let releaseSav2: ReleaseFn | null = null;
let releaseSav4b: ReleaseFn | null = null;
const listeners = new Set<() => void>();

export function getListeningModeOwner(): ListeningModeOwner {
  return owner;
}

export function subscribeListeningMode(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

function notify() {
  for (const fn of listeners) {
    try { fn(); } catch { /* */ }
  }
}

function silencePrevious(next: ListeningModeOwner) {
  if (owner === 'PHYSICAL_FIELD_C1' && next !== 'PHYSICAL_FIELD_C1' && releaseC1) {
    try { releaseC1(); } catch { /* */ }
  }
  if (owner === 'SELECTED_ORGANISM_SAV2' && next !== 'SELECTED_ORGANISM_SAV2' && releaseSav2) {
    try { releaseSav2(); } catch { /* */ }
  }
  if (owner === 'OFFLINE_SAV4B' && next !== 'OFFLINE_SAV4B' && releaseSav4b) {
    try { releaseSav4b(); } catch { /* */ }
  }
}

/**
 * Claim audible playback ownership. Previous owner is silenced/torn down first.
 * Visual panels may remain; only active audio ownership is exclusive.
 */
export function claimListeningMode(
  mode: 'PHYSICAL_FIELD_C1' | 'SELECTED_ORGANISM_SAV2' | 'OFFLINE_SAV4B',
  release: ReleaseFn,
): ListeningModeOwner {
  if (owner !== mode) {
    silencePrevious(mode);
  }
  owner = mode;
  if (mode === 'PHYSICAL_FIELD_C1') {
    releaseC1 = release;
  } else if (mode === 'SELECTED_ORGANISM_SAV2') {
    releaseSav2 = release;
  } else {
    releaseSav4b = release;
  }
  notify();
  return owner;
}

/** Release ownership if this mode currently owns playback. */
export function releaseListeningMode(
  mode: 'PHYSICAL_FIELD_C1' | 'SELECTED_ORGANISM_SAV2' | 'OFFLINE_SAV4B',
) {
  if (owner !== mode) {
    if (mode === 'PHYSICAL_FIELD_C1') releaseC1 = null;
    else if (mode === 'SELECTED_ORGANISM_SAV2') releaseSav2 = null;
    else releaseSav4b = null;
    return;
  }
  owner = 'OFF';
  if (mode === 'PHYSICAL_FIELD_C1') releaseC1 = null;
  else if (mode === 'SELECTED_ORGANISM_SAV2') releaseSav2 = null;
  else releaseSav4b = null;
  notify();
}

export function resetListeningModeForTests() {
  owner = 'OFF';
  releaseC1 = null;
  releaseSav2 = null;
  releaseSav4b = null;
}

/** Application exit: silence every registered listening owner. */
export function silenceAllListeningModes(): void {
  silencePrevious('OFF' as ListeningModeOwner);
  owner = 'OFF';
  releaseC1 = null;
  releaseSav2 = null;
  releaseSav4b = null;
  notify();
}
