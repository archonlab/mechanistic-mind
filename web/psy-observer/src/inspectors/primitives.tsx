import { useSyncExternalStore, type ReactNode } from 'react';
import { inspectorUiStore } from '../observer/stores';

export function InspectorAccordion({
  id,
  title,
  defaultOpen = true,
  children,
}: {
  id: string;
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const ui = useSyncExternalStore(inspectorUiStore.subscribe, inspectorUiStore.get, inspectorUiStore.get);
  const open = ui.accordions[id] ?? defaultOpen;
  return (
    <section className="insp-acc" data-accordion={id}>
      <button
        type="button"
        className="insp-acc-head"
        aria-expanded={open}
        onClick={() => {
          inspectorUiStore.set({
            ...inspectorUiStore.get(),
            accordions: { ...inspectorUiStore.get().accordions, [id]: !open },
          });
        }}
      >
        <span className="insp-acc-chevron">{open ? '▼' : '▶'}</span>
        {title}
      </button>
      {open && <div className="insp-acc-body">{children}</div>}
    </section>
  );
}

export function SemanticChip({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`insp-chip insp-chip-${kind.toLowerCase().replace(/\s+/g, '-')}`}>{children}</span>;
}

export function ReadOnlyMetric({ name, value, kind }: { name: string; value: any; kind?: string }) {
  const missing = value === undefined || value === null || value === '';
  return (
    <div className="metric insp-metric">
      <span>{name}{kind ? <SemanticChip kind={kind}>{kind}</SemanticChip> : null}</span>
      <strong className="insp-value">{missing ? '—' : String(value)}</strong>
    </div>
  );
}

export function MechanismToggle({
  label,
  enabled,
  onToggle,
  ablatable = true,
  live = true,
  description,
}: {
  label: string;
  enabled: boolean;
  onToggle?: () => void;
  ablatable?: boolean;
  live?: boolean;
  description?: string;
}) {
  const unavailable = !ablatable;
  const noHandler = !onToggle;
  const disabled = unavailable || noHandler;
  let reason = '';
  if (unavailable) reason = 'NOT INDEPENDENTLY ABLATABLE';
  else if (noHandler) reason = 'Control not wired';
  return (
    <div className="metric insp-metric" style={{ alignItems: 'center' }}>
      <span title={description}>
        {label}
        {live && ablatable ? <SemanticChip kind="LIVE">LIVE</SemanticChip> : null}
        {unavailable ? <SemanticChip kind="STATUS">STATUS</SemanticChip> : null}
      </span>
      <button
        type="button"
        className={enabled ? 'active' : ''}
        disabled={disabled}
        title={reason || (live ? 'LIVE mutable' : undefined)}
        onClick={() => onToggle?.()}
      >
        {unavailable ? 'READ ONLY' : enabled ? 'ON' : 'OFF'}
      </button>
      {disabled && reason ? <span className="subtle insp-why">{reason}</span> : null}
    </div>
  );
}

export function UnavailableControl({ label, reason }: { label: string; reason: string }) {
  return (
    <div className="metric insp-metric">
      <span>{label}<SemanticChip kind="UNAVAILABLE">UNAVAILABLE</SemanticChip></span>
      <strong className="subtle">{reason}</strong>
    </div>
  );
}

export function InspectorTabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <nav className="inspector-tabs" aria-label="Inspector section tabs">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className={active === t.id ? 'active' : ''}
          data-inspector-tab={t.id}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
