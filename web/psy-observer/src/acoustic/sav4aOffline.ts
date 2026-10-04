/** SAV4A constants — pure TS for node --test (no JSX). */
export const SAV4A_SCHEMA = 'SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1';
export const SAV4A_CAPABILITY = 'selected_organism_auditory_offline_reconstruction';
export const SAV4A_PROFILE = 'SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE_SAV4A_V1';
export const SAV4A_TITLE = 'OFFLINE AUDITORY RECONSTRUCTION · SAV4A';
export const SAV4A_WARNING_GAPS = 'GAPS ARE NOT SILENCE';
export const SAV4A_WARNING_TICK = '0.05 s/tick is canonical playback timing, not physical time';
export const SAV4A_WARNING_NO_AUDIO = 'No audio in SAV4A; playback belongs to SAV4B';

export function authorityBadge(auth: unknown): string {
  const a = String(auth || 'UNAVAILABLE');
  if (a.includes('OATT')) return 'OATT';
  if (a.includes('SAV1')) return 'SAV1';
  if (a.includes('LEGACY')) return 'LEGACY A5';
  return 'UNAVAILABLE';
}
