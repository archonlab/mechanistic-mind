/** Observer control / lifecycle receipt helpers (presentation only). */

export type LifecycleError = {
  code?: string;
  message?: string;
  recoverable?: boolean;
};

export type ControlReceipt = {
  operation?: string;
  accepted?: boolean;
  ok?: boolean;
  reason?: string;
  tick?: number;
  verified_final_tick?: number;
  lifecycle_state?: string;
  error?: LifecycleError;
};

export function lifecycleErrorCode(receipt: ControlReceipt | null | undefined): string | null {
  if (!receipt) return null;
  const code = receipt.error?.code;
  if (code) return String(code);
  if (receipt.accepted === false && String(receipt.operation || '').toUpperCase() === 'STOP') {
    const r = String(receipt.reason || '').toUpperCase();
    const msg = String(receipt.error?.message || '').toUpperCase();
    if (r.includes('HTTP_FAILED') || r.includes('NETWORKERROR') || msg.includes('NETWORKERROR') || msg.includes('HTTP_FAILED')) {
      return 'HTTP_FAILED';
    }
    if (r.includes('SAVE_FAILED') || r.includes('PERSISTENCE_INTEGRITY')) return 'SAVE_FAILED';
    if (r.includes('SAVE_STOP_IN_PROGRESS') || r.includes('SAVE_STOP_STARTED')) return null;
    return 'STOP_REJECTED';
  }
  return null;
}

export function mergeMechanismWarmState(prev: any[], warm: any): any[] {
  const incoming = Array.isArray(warm?.mechanisms) ? warm.mechanisms : [];
  if (warm?.catalog_included !== false && incoming.length && incoming.some((m: any) => m?.label || m?.description)) {
    return incoming;
  }
  if (!prev.length) return incoming;
  const byId = new Map<string, any>(incoming.map((m: any) => [String(m.id), m]));
  return prev.map((m: any) => {
    const w = byId.get(String(m.id));
    if (!w) return m;
    return { ...m, enabled: w.enabled, ablatable: w.ablatable ?? m.ablatable };
  });
}
