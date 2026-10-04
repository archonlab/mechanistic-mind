/** Singleton bridge for SAV2 restore/runtime teardown. */
import type { Sav2PlaybackEngine } from './sav2PlaybackEngine.ts';

let active: Sav2PlaybackEngine | null = null;

export function registerSav2Engine(engine: Sav2PlaybackEngine | null) {
  active = engine;
}

export function getRegisteredSav2Engine(): Sav2PlaybackEngine | null {
  return active;
}

export function notifySav2Restore() {
  active?.onRestore();
}

export function notifySav2RuntimeSwitch() {
  active?.onRestore();
}
