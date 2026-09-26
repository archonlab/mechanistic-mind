import { useEffect, useState } from 'react';
import { applyTheme, readThemePref, setThemePref, type ThemePref } from '../observer/theme';

const OPTIONS: { id: ThemePref; label: string }[] = [
  { id: 'system', label: 'System' },
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' },
];

export function ThemeControl() {
  const [pref, setPref] = useState<ThemePref>(() => readThemePref());

  useEffect(() => {
    applyTheme(pref);
    if (pref !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => applyTheme('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [pref]);

  return (
    <div className="lab-cluster theme-control" aria-label="Appearance">
      <span className="lab-kicker">THEME</span>
      {OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={pref === opt.id ? 'active' : ''}
          aria-pressed={pref === opt.id}
          onClick={() => {
            setThemePref(opt.id);
            setPref(opt.id);
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
