import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  registerResearcherAudio,
  resetResearcherAudioForTests,
  researcherAudioEngineCount,
  stopAllResearcherAudio,
} from './researcherAudio.ts';
import { C1PlaybackEngine } from './c1PlaybackEngine.ts';

describe('researcher audio process registry', () => {
  it('stopAllResearcherAudio tears down registered engines', async () => {
    resetResearcherAudioForTests();
    const engine = new C1PlaybackEngine({ fake: true });
    await engine.enableListening();
    assert.equal(researcherAudioEngineCount() >= 1, true);
    const n = stopAllResearcherAudio();
    assert.equal(n >= 1, true);
    assert.equal(engine.backend, null);
    resetResearcherAudioForTests();
  });
});
