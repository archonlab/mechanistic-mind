/** Derive compact HEARING indicator text from existing playback ownership (no new engines). */
import { getListeningModeOwner, type ListeningModeOwner } from './listeningModeOwner.ts';

export type HearingIndicatorKind =
  | 'OFF'
  | 'C1_ACTIVE'
  | 'SAV2_ACTIVE'
  | 'SAV4B_ACTIVE'
  | 'MUTED'
  | 'MAX_POLICY_MUTED'
  | 'UNAVAILABLE';

export function hearingIndicatorLabel(args: {
  owner?: ListeningModeOwner;
  muted?: boolean;
  maxPolicyMuted?: boolean;
  unavailable?: boolean;
}): string {
  if (args.unavailable) return 'HEARING · UNAVAILABLE';
  if (args.maxPolicyMuted) return 'HEARING · MAX POLICY MUTED';
  const owner = args.owner ?? getListeningModeOwner();
  if (owner === 'OFF') return 'HEARING · OFF';
  if (args.muted) return 'HEARING · MUTED';
  if (owner === 'PHYSICAL_FIELD_C1') return 'HEARING · C1 ACTIVE';
  if (owner === 'SELECTED_ORGANISM_SAV2') return 'HEARING · SAV2 ACTIVE';
  if (owner === 'OFFLINE_SAV4B') return 'HEARING · SAV4B OFFLINE';
  return 'HEARING · OFF';
}

export function hearingIndicatorKind(args: {
  owner?: ListeningModeOwner;
  muted?: boolean;
  maxPolicyMuted?: boolean;
  unavailable?: boolean;
}): HearingIndicatorKind {
  if (args.unavailable) return 'UNAVAILABLE';
  if (args.maxPolicyMuted) return 'MAX_POLICY_MUTED';
  const owner = args.owner ?? getListeningModeOwner();
  if (owner === 'OFF') return 'OFF';
  if (args.muted) return 'MUTED';
  if (owner === 'PHYSICAL_FIELD_C1') return 'C1_ACTIVE';
  if (owner === 'SELECTED_ORGANISM_SAV2') return 'SAV2_ACTIVE';
  if (owner === 'OFFLINE_SAV4B') return 'SAV4B_ACTIVE';
  return 'OFF';
}

export function listeningIsActive(owner?: ListeningModeOwner): boolean {
  const o = owner ?? getListeningModeOwner();
  return o === 'PHYSICAL_FIELD_C1' || o === 'SELECTED_ORGANISM_SAV2' || o === 'OFFLINE_SAV4B';
}
