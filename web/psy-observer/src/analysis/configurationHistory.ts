/**
 * Beta 2: MULTI_REGIME / STATIC configuration history from WORLD_INTERVENTION events.
 * Does not infer psychological effects — records regime boundaries only.
 */

export type RegimeReport = {
  configuration_history: 'STATIC' | 'MULTI_REGIME';
  n_interventions: number;
  n_regimes: number;
  regimes: Array<{
    regime_index: number;
    tick_start: number;
    tick_end: number | null;
    effective_fingerprint?: string | null;
  }>;
  interventions: Array<{
    tick: number;
    category: string | null;
    changes: Record<string, { old?: unknown; new?: unknown }> | null;
    fingerprint_before?: string | null;
    fingerprint_after?: string | null;
    history_reset: boolean;
    cognition_reset: boolean;
    body_reset: boolean;
    event_id?: string;
  }>;
  note?: string;
};

function isWorldIntervention(ev: any): boolean {
  const t = String(ev?.type || ev?.kind || '');
  return t === 'WORLD_INTERVENTION';
}

/** Collect WORLD_INTERVENTION events from frame + events arrays. */
export function collectWorldInterventions(input: {
  frame?: any;
  events?: any[];
}): any[] {
  const out: any[] = [];
  const seen = new Set<string>();
  const push = (ev: any) => {
    if (!isWorldIntervention(ev)) return;
    const id = String(ev.event_id || `${ev.simulation_tick ?? ev.tick}-${JSON.stringify(ev.changes || {})}`);
    if (seen.has(id)) return;
    seen.add(id);
    out.push(ev);
  };
  const fromFrame = input.frame?.world_interventions;
  if (Array.isArray(fromFrame)) fromFrame.forEach(push);
  if (Array.isArray(input.events)) input.events.forEach(push);
  const structured = input.frame?.structured_events;
  if (Array.isArray(structured)) structured.forEach(push);
  out.sort((a, b) => {
    const ta = Number(a.simulation_tick ?? a.tick ?? 0);
    const tb = Number(b.simulation_tick ?? b.tick ?? 0);
    if (ta !== tb) return ta - tb;
    return String(a.event_id || '').localeCompare(String(b.event_id || ''));
  });
  return out;
}

export function buildConfigurationHistory(
  interventions: any[],
  opts?: { start_tick?: number; end_tick?: number | null; initial_fingerprint?: string | null },
): RegimeReport {
  const start = Number(opts?.start_tick ?? 0);
  const end = opts?.end_tick ?? null;
  if (!interventions.length) {
    return {
      configuration_history: 'STATIC',
      n_interventions: 0,
      n_regimes: 1,
      regimes: [{
        regime_index: 0,
        tick_start: start,
        tick_end: end,
        effective_fingerprint: opts?.initial_fingerprint ?? null,
      }],
      interventions: [],
      note: 'No live WORLD_INTERVENTION events recorded.',
    };
  }
  const regimes: RegimeReport['regimes'] = [];
  const interOut: RegimeReport['interventions'] = [];
  let cursor = start;
  let fp = opts?.initial_fingerprint
    ?? interventions[0]?.effective_world_fingerprint_before
    ?? null;
  interventions.forEach((ev, i) => {
    const t = Number(ev.simulation_tick ?? ev.tick ?? 0);
    regimes.push({
      regime_index: i,
      tick_start: cursor,
      tick_end: t > cursor ? t - 1 : cursor,
      effective_fingerprint: fp,
    });
    interOut.push({
      tick: t,
      category: ev.intervention_category || ev.category || null,
      changes: ev.changes || ev.evidence?.changes || null,
      fingerprint_before: ev.effective_world_fingerprint_before ?? null,
      fingerprint_after: ev.effective_world_fingerprint_after ?? null,
      history_reset: Boolean(ev.history_reset),
      cognition_reset: Boolean(ev.cognition_reset),
      body_reset: Boolean(ev.body_reset),
      event_id: ev.event_id,
    });
    fp = ev.effective_world_fingerprint_after ?? fp;
    cursor = t;
  });
  regimes.push({
    regime_index: interventions.length,
    tick_start: cursor,
    tick_end: end,
    effective_fingerprint: fp,
  });
  return {
    configuration_history: 'MULTI_REGIME',
    n_interventions: interventions.length,
    n_regimes: regimes.length,
    regimes,
    interventions: interOut,
    note:
      'Configuration history is multi-regime. The final effective configuration '
      + 'must not be treated as if it existed for the entire biography.',
  };
}

export function formatConfigurationHistoryLog(report: RegimeReport): string[] {
  const lines: string[] = [];
  lines.push('CONFIGURATION HISTORY: ' + (report.configuration_history === 'MULTI_REGIME' ? 'MULTI-REGIME' : 'STATIC'));
  lines.push(`Interventions: ${report.n_interventions}  Regimes: ${report.n_regimes}`);
  if (report.note) lines.push(report.note);
  lines.push('');
  lines.push('WORLD / MECHANISM REGIMES');
  for (const r of report.regimes) {
    const end = r.tick_end == null ? '…' : String(r.tick_end);
    lines.push(`REGIME ${r.regime_index}`);
    lines.push(`  ticks: ${r.tick_start}–${end}`);
    if (r.effective_fingerprint) {
      lines.push(`  effective fingerprint: ${String(r.effective_fingerprint).slice(0, 16)}…`);
    }
    const next = report.interventions[r.regime_index];
    if (next) {
      lines.push(`INTERVENTION @ ${next.tick}`);
      lines.push(`  category: ${next.category || '—'}`);
      const ch = next.changes || {};
      for (const [k, v] of Object.entries(ch)) {
        lines.push(`  ${k}: ${String((v as any)?.old)} → ${String((v as any)?.new)}`);
      }
      lines.push(
        `  reset: history=${next.history_reset} cognition=${next.cognition_reset} body=${next.body_reset}`,
      );
    }
  }
  return lines;
}
