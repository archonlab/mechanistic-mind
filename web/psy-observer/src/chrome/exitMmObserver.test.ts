import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';

const here = dirname(fileURLToPath(import.meta.url));

describe('More → Exit MM Observer', () => {
  it('header source exposes Exit MM Observer and authenticated shutdown', () => {
    const src = readFileSync(join(here, 'ObserverHeader.tsx'), 'utf8');
    assert.match(src, /Exit MM Observer/);
    assert.match(src, /more-exit-mm-observer/);
    assert.match(src, /\/api\/instance\/shutdown/);
    assert.match(src, /stopAllResearcherAudio/);
    assert.match(src, /Closing MM Observer/);
    assert.match(src, /accessKey="q"/);
    assert.equal(src.includes('sendBeacon'), false);
    assert.equal(src.includes('beforeunload'), false);
  });
});
