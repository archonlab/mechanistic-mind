/** Analyzer job progress helpers — operational UI only, not scientific evidence. */

export const ANALYZER_ACTIVE_JOB_KEY = 'mm.observer.analyzer.activeJobId';
export const ANALYZER_OWNER_INSTANCE_KEY = 'mm.observer.analyzer.ownerInstanceId';
export const ANALYZER_OWNER_PACKAGE_KEY = 'mm.observer.analyzer.ownerPackageIdentity';
export const ANALYZER_LOG_OPEN_KEY = 'mm.observer.analyzer.logOpen';
export const INTERRUPTED_BY_APPLICATION_EXIT = 'INTERRUPTED_BY_APPLICATION_EXIT';
export const INTERRUPTED_USER_MESSAGE = 'Previous analysis was interrupted when MM Observer closed.';

export type AnalyzerJobProgress = {
  job_id?: string;
  schema?: string;
  state?: string;
  status?: string;
  phase?: string;
  phase_id?: string;
  phase_label?: string;
  phase_index?: number | null;
  phase_count?: number | null;
  completed_units?: number | null;
  total_units?: number | null;
  phase_processed?: number | null;
  phase_total?: number | null;
  overall_processed?: number | null;
  overall_total?: number | null;
  percent?: number | null;
  status_text?: string;
  message?: string;
  terminal?: boolean;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  last_progress_at?: string | null;
  worker_heartbeat_at?: string | null;
  heartbeat_at?: string | null;
  elapsed_seconds?: number | null;
  elapsed_s?: number | null;
  records_per_second?: number | null;
  unit_label?: string | null;
  snapshot_terminal_tick?: number | null;
  snapshot_record_count?: number | null;
  current_operation?: string | null;
  recent_log?: Array<{ ts?: string; message?: string }>;
  alive?: boolean | null;
  ui_health?: string | null;
  owner_instance_id?: string | null;
  owner_package_identity?: string | null;
};

export function loadActiveJobId(): string | null {
  try {
    return localStorage.getItem(ANALYZER_ACTIVE_JOB_KEY);
  } catch {
    return null;
  }
}

export function saveActiveJobId(jobId: string | null, owner?: { instanceId?: string | null; packageIdentity?: string | null }): void {
  try {
    if (!jobId) {
      localStorage.removeItem(ANALYZER_ACTIVE_JOB_KEY);
      localStorage.removeItem(ANALYZER_OWNER_INSTANCE_KEY);
      localStorage.removeItem(ANALYZER_OWNER_PACKAGE_KEY);
      return;
    }
    localStorage.setItem(ANALYZER_ACTIVE_JOB_KEY, jobId);
    if (owner?.instanceId) localStorage.setItem(ANALYZER_OWNER_INSTANCE_KEY, owner.instanceId);
    if (owner?.packageIdentity) localStorage.setItem(ANALYZER_OWNER_PACKAGE_KEY, owner.packageIdentity);
  } catch {
    /* ignore */
  }
}

export function jobRestoreAllowed(
  job: AnalyzerJobProgress | null | undefined,
  health: { instance_id?: string | null; package_identity?: string | null } | null | undefined,
  storedOwner?: { instanceId?: string | null; packageIdentity?: string | null },
): boolean {
  if (!job || !health?.instance_id || !health?.package_identity) return false;
  const state = String(job.state || job.status || '').toUpperCase();
  if (job.terminal === true) return false;
  if (['COMPLETED', 'COMPLETE', 'FAILED', 'CANCELLED', INTERRUPTED_BY_APPLICATION_EXIT].includes(state)) {
    return false;
  }
  const jobInst = String((job as any).owner_instance_id || storedOwner?.instanceId || '');
  const jobPkg = String((job as any).owner_package_identity || storedOwner?.packageIdentity || '');
  if (jobInst && jobInst !== String(health.instance_id)) return false;
  if (jobPkg && jobPkg !== String(health.package_identity)) return false;
  if (!jobInst || !jobPkg) return false;
  return true;
}

export function loadLogOpenPref(): boolean {
  try {
    return localStorage.getItem(ANALYZER_LOG_OPEN_KEY) === '1';
  } catch {
    return false;
  }
}

export function saveLogOpenPref(open: boolean): void {
  try {
    localStorage.setItem(ANALYZER_LOG_OPEN_KEY, open ? '1' : '0');
  } catch {
    /* ignore */
  }
}

export function secondsAgo(iso: string | null | undefined, nowMs = Date.now()): number | null {
  if (!iso) return null;
  const t = Date.parse(String(iso));
  if (!Number.isFinite(t)) return null;
  return Math.max(0, Math.round((nowMs - t) / 1000));
}

export function deriveUiState(prog: AnalyzerJobProgress | null | undefined, nowMs = Date.now()): {
  banner: string;
  healthNote: string;
} {
  if (!prog) return { banner: 'ANALYSIS: IDLE', healthNote: '' };
  const state = String(prog.state || prog.status || '').toUpperCase();
  if (state === 'FAILED') return { banner: 'ANALYSIS: FAILED', healthNote: String(prog.error_message || prog.error_code || '') };
  if (state === 'INTERRUPTED_BY_APPLICATION_EXIT') {
    return { banner: 'ANALYSIS: INTERRUPTED', healthNote: INTERRUPTED_USER_MESSAGE };
  }
  if (state === 'CANCELLED') return { banner: 'ANALYSIS: CANCELLED', healthNote: '' };
  if (state === 'COMPLETED' || state === 'COMPLETE') return { banner: 'ANALYSIS: COMPLETED', healthNote: '' };
  if (state === 'CANCEL_REQUESTED') return { banner: 'ANALYSIS: CANCEL REQUESTED', healthNote: 'Stopping at next safe point' };
  if (state === 'QUEUED') return { banner: 'ANALYSIS: QUEUED', healthNote: 'Waiting for worker' };

  const hb = secondsAgo(prog.worker_heartbeat_at || prog.heartbeat_at || prog.updated_at, nowMs);
  const lp = secondsAgo(prog.last_progress_at, nowMs);
  const op = String(prog.current_operation || prog.status_text || '').trim();
  if (prog.alive === false || prog.ui_health === 'WORKER_UNREACHABLE') {
    return { banner: 'WORKER HEARTBEAT LOST', healthNote: 'No recent worker heartbeat — checking status' };
  }
  if (hb != null && hb > 15) {
    return { banner: 'WORKER HEARTBEAT LOST', healthNote: `No heartbeat for ${hb}s` };
  }
  // Heartbeat alive ≠ useful work progressed.
  if (lp != null && lp >= 60) {
    const mins = Math.max(1, Math.round(lp / 60));
    return {
      banner: `NO USEFUL PROGRESS FOR ${mins} MINUTES`,
      healthNote: `Heartbeat alive · last useful progress ${lp}s ago${op ? ` · ${op}` : ''}`,
    };
  }
  if (lp != null && lp > 20) {
    return {
      banner: 'WORKING — long operation, heartbeat alive',
      healthNote: `Heartbeat ≠ progress · last useful progress ${lp}s ago${op ? ` · ${op}` : ''}`,
    };
  }
  return {
    banner: 'WORKING — useful progress observed',
    healthNote: hb != null ? `Heartbeat ${hb}s ago${op ? ` · ${op}` : ''}` : (op || 'Working'),
  };
}

export function formatLogLine(entry: { ts?: string; message?: string }): string {
  const ts = entry.ts ? String(entry.ts).slice(11, 19) : '--:--:--';
  return `${ts}  ${String(entry.message || '').trim()}`;
}
