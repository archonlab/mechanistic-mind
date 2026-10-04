/** Process-wide researcher playback registry. Used on application exit. */

export type StoppableAudio = {
  stop?: () => void;
  teardown?: () => void;
};

const engines = new Set<StoppableAudio>();

export function registerResearcherAudio(engine: StoppableAudio): () => void {
  engines.add(engine);
  return () => {
    engines.delete(engine);
  };
}

export function stopAllResearcherAudio(): number {
  let n = 0;
  for (const engine of [...engines]) {
    try {
      if (typeof engine.stop === 'function') {
        engine.stop();
        n += 1;
        continue;
      }
    } catch { /* continue */ }
    try {
      if (typeof engine.teardown === 'function') {
        engine.teardown();
        n += 1;
      }
    } catch { /* continue */ }
  }
  return n;
}

export function researcherAudioEngineCount(): number {
  return engines.size;
}

export function resetResearcherAudioForTests(): void {
  engines.clear();
}
