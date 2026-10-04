/** Singleton bridge so App restore/preset can tear down C1 without props drilling. */
import type { C1PlaybackEngine } from './c1PlaybackEngine.ts';

let active: C1PlaybackEngine | null = null;

export function registerC1Engine(engine: C1PlaybackEngine | null) {
  active = engine;
}

export function getRegisteredC1Engine(): C1PlaybackEngine | null {
  return active;
}

export function notifyC1Restore() {
  active?.onRestore();
}

export function notifyC1RuntimeSwitch() {
  active?.onRestore();
}
