/** Singleton bridge for SAV4B teardown from HEARING mode OFF / live claims. */
import type { Sav4bPlaybackEngine } from './sav4bPlaybackEngine.ts';

let active: Sav4bPlaybackEngine | null = null;

export function registerSav4bEngine(engine: Sav4bPlaybackEngine | null) {
  active = engine;
}

export function getRegisteredSav4bEngine(): Sav4bPlaybackEngine | null {
  return active;
}

export function notifySav4bRestore() {
  // Playback is not simulation state — stop audible offline only.
  active?.stop();
}
