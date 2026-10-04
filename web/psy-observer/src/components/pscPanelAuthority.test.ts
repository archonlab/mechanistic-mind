/** PSC four-authority presentation: current runtime first, next-run qualified. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const app = readFileSync(join(root, '../App.tsx'), 'utf8');
const motor = readFileSync(join(root, 'PscMotorResolutionControl.tsx'), 'utf8');
const css = readFileSync(join(root, '../styles/app.css'), 'utf8');
const dock = readFileSync(join(root, '../inspectors/InspectorDock.tsx'), 'utf8');
const header = readFileSync(join(root, '../chrome/ObserverHeader.tsx'), 'utf8');
const hearing = readFileSync(join(root, '../acoustic/hearingPlaybackStatus.ts'), 'utf8');
const dualLife = readFileSync(join(root, 'eyeDockDualFpvLifecycle.ts'), 'utf8');
const analyzer = readFileSync(join(root, '../analysis/analyzerJobProgress.ts'), 'utf8')
  + readFileSync(join(root, 'AnalyzeResultsPanel.tsx'), 'utf8');

const pscStart = app.indexOf("if (tabId === 'psc')");
const pscEnd = app.indexOf("if (tabId === 'ablations')");
const psc = app.slice(pscStart, pscEnd);

describe('PSC UI four-authority contract', () => {
  it('renders CURRENT RUNTIME before NEXT RUN', () => {
    const cur = psc.indexOf('CURRENT RUNTIME');
    const next = psc.indexOf('NEXT RUN');
    assert.ok(cur >= 0 && next > cur);
    const curTest = psc.indexOf('psc-current-run-summary');
    const nextTest = psc.indexOf('psc-next-run-summary');
    assert.ok(curTest >= 0 && nextTest > curTest);
  });

  it('current runtime uses live overlay helper, not draft fallback', () => {
    assert.match(psc, /currentRuntimePresentation/);
    assert.match(psc, /experiment\?\.runtime\?\.psc_schedule/);
    assert.doesNotMatch(psc, /runtimeSched\.psc \|\| pscOn/);
    assert.match(psc, /unavailable/);
  });

  it('qualifies next-run initial OFF and never shows unqualified READY — PSC OFF', () => {
    assert.match(psc, /nextRunInitialLabel/);
    assert.match(motor, /deferredMotorStatus/);
    assert.doesNotMatch(psc, /READY — PSC OFF/);
    assert.doesNotMatch(motor, /READY — PSC OFF/);
  });

  it('shows enabled-at, transition count, armed, withhold', () => {
    assert.match(psc, /Enabled at tick/);
    assert.match(psc, /Transition count/);
    assert.match(psc, /Armed/);
    assert.match(psc, /Withhold gate/);
  });

  it('applied configuration is labelled initial/frozen and does not override live', () => {
    assert.match(psc, /APPLIED CONFIGURATION · initial \/ frozen/);
    assert.match(psc, /Do not override CURRENT RUNTIME|do not override CURRENT RUNTIME/);
    assert.match(psc, /OFF \(initial\)/);
  });

  it('OBSERVED_COMPOSITE remains experimental and is not PSC ON/OFF', () => {
    assert.match(psc, /EXPERIMENTAL STATUS/);
    assert.match(psc, /not current PSC ON\/OFF/);
    assert.match(motor, /EXPERIMENTAL/);
  });

  it('one global Apply; display-only PSC panel has no per-tab apply', () => {
    assert.ok(dock.includes('experiment-apply-bar'));
    assert.equal(psc.includes('apply-experiment'), false);
    assert.equal(psc.includes('APPLY LIVE'), false);
  });

  it('constrained layout keeps current runtime visible', () => {
    assert.match(css, /psc-runtime-panel/);
    assert.match(css, /overflow:visible/);
  });

  it('keyboard help remains on PSC schedule', () => {
    assert.match(psc, /SettingInfoHelp/);
    assert.match(psc, /info-psc-draft-schedule/);
  });

  it('Dual FPV, Hearing honesty, Analyzer, More Exit remain wired', () => {
    assert.match(dualLife, /wantEyeDockDualFpvSubscription/);
    assert.match(hearing, /SIGNAL/);
    assert.match(hearing, /TRUE ZERO/);
    assert.match(hearing, /NO SOURCE/);
    assert.match(hearing, /UNAVAILABLE/);
    assert.match(analyzer, /heartbeat|progress/i);
    assert.match(header, /more-exit-mm-observer/);
  });
});
