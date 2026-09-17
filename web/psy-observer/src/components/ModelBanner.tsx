type Props = { banner: any; header?: any };

export function ModelBanner({ banner, header }: Props) {
  if (!banner && !header) return null;
  const family = banner?.model_family || header?.model_family || 'Mechanistic Mind';
  const version = banner?.model_version || header?.model_version || '1.0';
  const codename = banner?.model_codename || header?.model_codename || 'Tiktaalik';
  const classification = banner?.classification || header?.runtime_classification || 'CANONICAL';
  const canonical = banner?.canonical ?? header?.canonical ?? true;
  const en = banner?.mechanisms?.enabled || {};
  const chips = Object.entries(en)
    .filter(([, v]) => v)
    .map(([k]) => k.replace(/_/g, ' '))
    .slice(0, 6);
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        alignItems: 'center',
        padding: '6px 10px',
        marginBottom: 8,
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: 6,
        fontSize: 12,
      }}
    >
      <span style={{ fontWeight: 700, letterSpacing: 0.3 }}>{family.toUpperCase()}</span>
      <span style={{ color: '#86efac', fontWeight: 700 }}>MM {version}</span>
      <span style={{ color: '#fde68a', fontWeight: 700 }}>{codename.toUpperCase()}</span>
      <span className="muted">|</span>
      <span style={{ color: canonical ? '#86efac' : '#fbbf24' }}>{classification}</span>
      {chips.map((c) => (
        <span key={c} style={{ background: '#14532d', padding: '1px 6px', borderRadius: 4 }}>{c}</span>
      ))}
    </div>
  );
}
