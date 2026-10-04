/** Pure PSC panel authority — presentation only, never mutates runtime. */

export type PscScheduleLike = {
  psc?: string | number | null;
  schedule?: number | string | null;
  armed?: boolean | null;
  activated_tick?: number | string | null;
  transition_count?: number | string | null;
  withhold_opened?: boolean | null;
};

export type CurrentRuntimePresentation = {
  pscLabel: 'ON' | 'OFF' | 'unavailable';
  summary: string;
  enabledAt: string | null;
  transitionCount: string | null;
  scheduleLabel: string | null;
  armedLabel: string | null;
  withholdLabel: string | null;
  unavailable: boolean;
};

function hasLiveSchedule(sched: PscScheduleLike | null | undefined): boolean {
  if (!sched || typeof sched !== 'object') return false;
  const psc = sched.psc;
  return psc != null && String(psc).trim() !== '' && String(psc) !== '—';
}

export function currentRuntimePresentation(
  sched: PscScheduleLike | null | undefined,
): CurrentRuntimePresentation {
  if (!hasLiveSchedule(sched)) {
    return {
      pscLabel: 'unavailable',
      summary: 'unavailable',
      enabledAt: null,
      transitionCount: null,
      scheduleLabel: null,
      armedLabel: null,
      withholdLabel: null,
      unavailable: true,
    };
  }
  const psc = String(sched!.psc).toUpperCase() === 'ON' ? 'ON' : 'OFF';
  const schedule = sched!.schedule;
  const activated = sched!.activated_tick;
  const transitions = sched!.transition_count;
  const armed = Boolean(sched!.armed);
  const withhold = sched!.withhold_opened;
  let summary: string;
  if (psc === 'ON') {
    summary = activated != null && activated !== '' ? `ON · enabled at tick ${activated}` : 'ON';
  } else if (armed && schedule != null && schedule !== 'MANUAL') {
    summary = `OFF · scheduled at tick ${schedule}`;
  } else if (schedule == null || schedule === 'MANUAL') {
    summary = 'no schedule applied';
  } else {
    summary = `OFF · schedule ${schedule}`;
  }
  return {
    pscLabel: psc,
    summary,
    enabledAt: activated != null && activated !== '' ? String(activated) : null,
    transitionCount: transitions != null && transitions !== '' ? String(transitions) : null,
    scheduleLabel:
      schedule == null || schedule === 'MANUAL'
        ? 'MANUAL'
        : `Tick ${schedule}`,
    armedLabel: armed ? 'armed' : 'disarmed',
    withholdLabel:
      withhold === true ? 'open' : withhold === false ? 'closed' : null,
    unavailable: false,
  };
}

export function nextRunScheduleLabel(draftTicks: number | null | undefined): string {
  if (draftTicks == null) return 'no schedule';
  return `scheduled at tick ${draftTicks}`;
}

export function nextRunInitialLabel(initialOn: boolean): string {
  return initialOn ? 'ON (next run)' : 'OFF (next run)';
}

export function deferredMotorStatus(initialOn: boolean): string {
  return initialOn ? 'NEXT RUN · INITIAL ON' : 'NEXT RUN · INITIAL OFF';
}

export function liveMotorStatus(args: { pscCurrentlyOn: boolean; observedComposite: boolean }): string {
  if (!args.pscCurrentlyOn) {
    return args.observedComposite ? 'CURRENT RUNTIME · PSC OFF' : 'CURRENT RUNTIME · PSC OFF';
  }
  return args.observedComposite ? 'CURRENT RUNTIME · EXPERIMENTAL' : 'CURRENT RUNTIME · PSC ON';
}
