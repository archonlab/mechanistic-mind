/** Accessible ⓘ setting help — tooltip on hover/focus, persistent popover on click. */

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

type Props = {
  label: string;
  brief: string;
  detail?: ReactNode;
  testId?: string;
};

/**
 * Class A UI only — never mutates experiment draft or runtime.
 */
export function SettingInfoHelp({ label, brief, detail, testId }: Props) {
  const id = useId();
  const popoverId = `${id}-popover`;
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (popRef.current?.contains(t) || btnRef.current?.contains(t)) return;
      setOpen(false);
      btnRef.current?.focus();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDoc);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDoc);
    };
  }, [open]);

  return (
    <span className="setting-info-help" data-testid={testId || 'setting-info-help'}>
      <button
        ref={btnRef}
        type="button"
        className="setting-info-btn"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={popoverId}
        title={brief}
        onClick={() => setOpen((v) => !v)}
      >
        ⓘ
      </button>
      {open ? (
        <div
          ref={popRef}
          id={popoverId}
          role="dialog"
          aria-label={`${label} help`}
          className="setting-info-popover"
          data-testid="setting-info-popover"
        >
          <strong className="setting-info-popover-title">{label}</strong>
          <p className="setting-info-popover-brief">{brief}</p>
          {detail ? <div className="setting-info-popover-detail">{detail}</div> : null}
        </div>
      ) : null}
    </span>
  );
}
