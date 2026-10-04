/** Honest researcher-playback status. Never a scientific evidence claim. */

export type HearingPlaybackStatus =
  | 'STOPPED'
  | 'STARTING'
  | 'LIVE · SIGNAL'
  | 'LIVE · TRUE ZERO'
  | 'LIVE · NO SOURCE'
  | 'UNAVAILABLE'
  | 'AUDIO CONTEXT SUSPENDED'
  | 'OUTPUT ERROR';

export type HearingPlaybackClassification = {
  status: HearingPlaybackStatus;
  sourceMode: 'World' | string;
  latestTick: number | null;
  signalLevel: number;
  masterVolume: number;
  audioContextState: string;
  explanation: string;
};

function peakAbs(samples: number[] | null | undefined): number {
  if (!Array.isArray(samples) || !samples.length) return 0;
  let m = 0;
  for (const v of samples) {
    const a = Math.abs(Number(v) || 0);
    if (a > m) m = a;
  }
  return m;
}

export function classifyHearingPlayback(args: {
  listening: boolean;
  audioContextState?: string | null;
  sourceAvailable?: boolean;
  trueZero?: boolean;
  mappedAmplitudes?: number[] | null;
  energyBands?: number[] | null;
  outputError?: boolean;
  starting?: boolean;
  sourceMode: 'World' | string;
  latestTick?: number | null;
  masterVolume?: number;
}): HearingPlaybackClassification {
  const audio = String(args.audioContextState || 'closed');
  const level = Math.max(peakAbs(args.mappedAmplitudes), peakAbs(args.energyBands));
  const volume = Number.isFinite(args.masterVolume) ? Number(args.masterVolume) : 0;
  const base = {
    sourceMode: args.sourceMode,
    latestTick: args.latestTick ?? null,
    signalLevel: level,
    masterVolume: volume,
    audioContextState: audio,
  };
  if (args.outputError) {
    return {
      ...base,
      status: 'OUTPUT ERROR',
      explanation: 'The Web Audio graph failed to reach the destination. Researcher playback only.',
    };
  }
  if (!args.listening && !args.starting) {
    return {
      ...base,
      status: 'STOPPED',
      explanation: 'Playback is stopped. Organism hearing and scientific capture continue.',
    };
  }
  if (audio === 'suspended') {
    return {
      ...base,
      status: 'AUDIO CONTEXT SUSPENDED',
      explanation: 'The browser suspended AudioContext. A Live click (user gesture) resumes it.',
    };
  }
  if (args.starting || (args.listening && audio !== 'running' && audio !== 'closed')) {
    return {
      ...base,
      status: 'STARTING',
      explanation: 'Playback was requested; waiting for AudioContext running.',
    };
  }
  if (!args.sourceAvailable) {
    return {
      ...base,
      status: args.listening ? 'LIVE · NO SOURCE' : 'UNAVAILABLE',
      explanation: 'No retained auditory payload for this source. Missing is not silence.',
    };
  }
  if (args.trueZero || (args.listening && level <= 0)) {
    return {
      ...base,
      status: args.sourceAvailable ? 'LIVE · TRUE ZERO' : 'LIVE · NO SOURCE',
      explanation: args.trueZero || args.sourceAvailable
        ? 'Source is present and currently zero. Silence here is honest, not an engine failure.'
        : 'No retained auditory payload for this source.',
    };
  }
  if (args.listening && audio === 'running') {
    return {
      ...base,
      status: 'LIVE · SIGNAL',
      explanation: 'Audio graph is running with a nonzero mapped source. Researcher playback only.',
    };
  }
  if (args.listening) {
    return {
      ...base,
      status: 'STARTING',
      explanation: 'Listening is armed; AudioContext is not yet running.',
    };
  }
  return {
    ...base,
    status: 'UNAVAILABLE',
    explanation: 'Playback cannot be classified as live. Missing is not rendered as silence.',
  };
}
