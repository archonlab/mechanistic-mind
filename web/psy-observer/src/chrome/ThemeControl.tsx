import { useEffect, useState } from 'react';
import { applyTheme, readThemePref, setThemePref, type ThemePref } from '../observer/theme';

const OPTIONS: { id: ThemePref; label: string }[] = [
  { id: 'system', label: 'System' },
  { id: 'dark', label: 'Dark' },
  { id: 'light', label: 'Light' },
  { id: 'aquatic', label: 'Aquatic' },
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
    <div className="theme-control" aria-label="Appearance">
      <select
        aria-label="Theme"
        value={pref}
        onChange={(e) => {
          const next = e.target.value as ThemePref;
          setThemePref(next);
          setPref(next);
        }}
      >
        {OPTIONS.map((opt) => (
          <option key={opt.id} value={opt.id}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}
