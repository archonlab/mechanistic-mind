/** Bottom HUD action label: final applied composite motor when present. */

export function observerHudActionLabel(agent: any, fallback?: string | null): string {
  const composite = agent?.composite_action_display;
  if (composite) return String(composite);
  return String(agent?.selected_action || fallback || '—');
}

export function hudActionRows(frame: any, selectedAgentId: string) {
  const header = frame.header || {};
  const body = frame.body || {};
  const physical = frame.physical || {};
  const agentsObs = frame.agents_observer || [];
  const physicalFallback =
    physical?.composite_action_display
    || physical?.selected_action
    || header.selected_action
    || body?.selected_action;
  return (agentsObs.length
    ? agentsObs
    : [{
        observer_id: selectedAgentId || 'agent_0',
        selected_action: physicalFallback,
        composite_action_display: physical?.composite_action_display,
      }]
  ).map((a: any, i: number) => {
    const id = a.observer_id || a.agent_id || `agent_${i}`;
    const peerFallback = (id === selectedAgentId) ? physicalFallback : null;
    const actionLabel = observerHudActionLabel(a, peerFallback);
    return { id, actionLabel };
  });
}
