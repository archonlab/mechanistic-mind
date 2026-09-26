/**
 * Observe V2 — live buffer identity / invalidation.
 * Prevents stale run/generation evidence from appearing as current.
 */

export type ObserveBufferIdentity = {
  run_id: string;
  generation: string | number;
  agent_id: string;
};

export function observeBufferIdentityFromFrame(
  frame: any,
  opts?: { run_id?: string | null; agent_id?: string | null },
): ObserveBufferIdentity {
  const header = frame?.header || {};
  return {
    run_id: String(opts?.run_id || header.run_id || frame?.run_id || ''),
    generation: header.runtime_generation ?? frame?.observation?.runtime_generation ?? '',
    agent_id: String(
      opts?.agent_id
      || frame?.observer?.selected_agent_id
      || header.selected_agent_id
      || '',
    ),
  };
}

export function observeBufferIdentityChanged(
  prev: ObserveBufferIdentity | null | undefined,
  next: ObserveBufferIdentity,
): { changed: boolean; reason: string | null } {
  if (!prev) return { changed: false, reason: null };
  if (String(prev.run_id) !== String(next.run_id) && next.run_id && prev.run_id) {
    return { changed: true, reason: 'run_id' };
  }
  if (String(prev.generation) !== String(next.generation) && next.generation !== '' && prev.generation !== '') {
    return { changed: true, reason: 'generation' };
  }
  if (String(prev.agent_id) !== String(next.agent_id) && next.agent_id && prev.agent_id) {
    return { changed: true, reason: 'agent_id' };
  }
  return { changed: false, reason: null };
}

/**
 * Filter events/timeline rows that do not match current generation when tagged.
 * Rows without generation tags are kept (server may not stamp every event).
 */
export function filterRowsForIdentity(
  rows: any[],
  identity: ObserveBufferIdentity,
): any[] {
  if (!rows?.length) return [];
  const gen = identity.generation;
  if (gen === '' || gen == null) return rows.slice();
  return rows.filter((r) => {
    const g = r?.runtime_generation ?? r?.generation ?? r?.evidence?.runtime_generation;
    if (g == null || g === '') return true;
    return String(g) === String(gen);
  });
}

export function shouldInvalidateObserveBuffers(
  prev: ObserveBufferIdentity | null | undefined,
  next: ObserveBufferIdentity,
): boolean {
  const { changed, reason } = observeBufferIdentityChanged(prev, next);
  // Agent switch invalidates CURRENT STATE display but events may be multi-agent;
  // still clear selectedEvent / agent-scoped current. For events, invalidate on run/gen.
  if (!changed) return false;
  return reason === 'run_id' || reason === 'generation' || reason === 'agent_id';
}

export function invalidateEventsOnRunOrGeneration(
  prev: ObserveBufferIdentity | null | undefined,
  next: ObserveBufferIdentity,
): boolean {
  const { changed, reason } = observeBufferIdentityChanged(prev, next);
  return changed && (reason === 'run_id' || reason === 'generation');
}
