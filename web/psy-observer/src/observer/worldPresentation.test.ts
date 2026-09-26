import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { resolvedWorldTheme, worldChrome } from './worldPresentation.ts';

describe('world presentation theme', () => {
  it('resolves light only from data-theme=light', () => {
    assert.equal(resolvedWorldTheme({ dataset: { theme: 'light' } } as any), 'light');
    assert.equal(resolvedWorldTheme({ dataset: { theme: 'dark' } } as any), 'dark');
    assert.equal(resolvedWorldTheme({ dataset: {} } as any), 'dark');
  });

  it('keeps class order and agent FOV slots; light stage is not dark', () => {
    const d = worldChrome('dark');
    const l = worldChrome('light');
    assert.equal(d.classColors.length, 6);
    assert.equal(l.classColors.length, 6);
    assert.equal(d.fov.length, l.fov.length);
    assert.equal(d.stage, '#070b10');
    assert.match(l.stage, /^#d4dce6$/i);
    assert.notEqual(l.stage, d.stage);
  });
});
