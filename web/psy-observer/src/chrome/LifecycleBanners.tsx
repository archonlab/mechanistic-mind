import { memo } from 'react';
import { lifecycleErrorCode } from '../lifecycleReceipt';
import { useLifecycleStore, useStatusStore } from '../observer/useExternalStore';

export const LifecycleBanners = memo(function LifecycleBanners() {
  const { controlMessage, saveBanner, finalizing } = useLifecycleStore();
  const status = useStatusStore();
  const frozen = Boolean(status.displayFrozen)
    || (String(status.executionMode || '').toUpperCase() === 'HEADLESS'
      && (status.status === 'RUNNING'));
  const disconnected = status.connection === 'DISCONNECTED';

  return (
    <div className="lifecycle-banners" data-testid="lifecycle-banners">
      {disconnected && (
        <div className="control-receipt bad" role="alert">
          SERVER_UNAVAILABLE — Observer disconnected. Controls are disabled. Last world image is not a live tick.
        </div>
      )}
      {finalizing && <div className="control-receipt warn-banner">{finalizing}</div>}
      {frozen && !disconnected && (
        <div className="control-receipt warn-banner" data-testid="headless-frozen">
          DISPLAY FROZEN @ t{status.displayTick ?? '—'} · RUNTIME @ t{status.simTick ?? status.tick ?? '—'} · HEADLESS (no live capture)
        </div>
      )}
      {saveBanner && !saveBanner.failed && !saveBanner.discarded && (
        <div className="control-receipt ok">
          SAVED · t{saveBanner.tick} · verified snapshot tick: {saveBanner.tick}
          {saveBanner.seed != null ? ` · Seed ${saveBanner.seed}` : ''}
          <div className="subtle">Path: {saveBanner.path}</div>
        </div>
      )}
      {saveBanner?.failed && saveBanner.layer === 'http' && (
        <div className="control-receipt bad" data-testid="save-http-failed-banner">
          HTTP_FAILED — {saveBanner.error} Disk save is not confirmed from this error. Poll save-job or inspect live/tmp directories.
        </div>
      )}
      {saveBanner?.failed && saveBanner.layer !== 'http' && (
        <div className="control-receipt bad" data-testid="save-failed-banner">
          SAVE_FAILED — {saveBanner.error}. Live state preserved; try Save &amp; Stop again.
          {saveBanner.liveTick != null ? ` · live tick: ${saveBanner.liveTick}` : ''}
          {saveBanner.capturedTick != null ? ` · captured tick: ${saveBanner.capturedTick}` : ''}
        </div>
      )}
      {saveBanner?.discarded && (
        <div className="control-receipt warn-banner">
          Stopped without saving ({saveBanner.reason}). No completed run artifact was written.
        </div>
      )}
      {controlMessage && (
        <div className={`control-receipt ${controlMessage.accepted ? 'ok' : 'bad'}`} data-testid="control-receipt">
          {controlMessage.operation}: {controlMessage.accepted ? 'ACCEPTED' : 'REJECTED'}
          {lifecycleErrorCode(controlMessage) ? ` · ${lifecycleErrorCode(controlMessage)}` : ''}
          {' '}· t{controlMessage.verified_final_tick ?? controlMessage.tick}
          {controlMessage.error?.message || controlMessage.reason
            ? ` — ${controlMessage.error?.message || controlMessage.reason}`
            : ''}
        </div>
      )}
    </div>
  );
});
