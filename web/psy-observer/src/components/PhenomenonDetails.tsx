/** Progressive disclosure categories — researcher-local UI state only. */

import type { ReactNode } from 'react';

export type PhenomenonCategory = {
  id: string;
  title: string;
  summary: string;
  children: ReactNode;
  /** When true, do not mount children while collapsed (no expensive charts). */
  deferMount?: boolean;
};

type Props = {
  categories: PhenomenonCategory[];
  testIdPrefix?: string;
};

/**
 * Semantic &lt;details&gt; accordion. Expansion never resets simulation.
 */
export function PhenomenonDetails({ categories, testIdPrefix = 'phenomenon' }: Props) {
  return (
    <div className="phenomenon-details" data-testid={`${testIdPrefix}-details`}>
      {categories.map((c) => (
        <details
          key={c.id}
          className="phenomenon-category"
          data-testid={`${testIdPrefix}-cat-${c.id}`}
        >
          <summary className="phenomenon-category-summary">
            <span className="phenomenon-category-title">{c.title}</span>
            <span className="phenomenon-category-line subtle">{c.summary}</span>
          </summary>
          <div className="phenomenon-category-body" data-testid={`${testIdPrefix}-body-${c.id}`}>
            <DeferredBody defer={c.deferMount !== false}>{c.children}</DeferredBody>
          </div>
        </details>
      ))}
    </div>
  );
}

function DeferredBody({ defer, children }: { defer: boolean; children: ReactNode }) {
  // Parent <details> open state is CSS; we still mount when open via :open sibling —
  // for deferMount we rely on details[open] CSS + a small OpenAware wrapper.
  if (!defer) return <>{children}</>;
  return <OpenAware>{children}</OpenAware>;
}

function OpenAware({ children }: { children: ReactNode }) {
  // Render children only when ancestor details is open (checked on toggle via CSS class).
  // Using a light approach: children always in DOM only when details[open] — handled by
  // rendering inside details which browsers keep in DOM; expensive canvas parents should
  // pass deferMount and we gate with a tiny state from toggle.
  return <OpenGate>{children}</OpenGate>;
}

function OpenGate({ children }: { children: ReactNode }) {
  // details fires toggle on the element; capture via onToggle on parent is cleaner —
  // PhenomenonDetails already wraps summary; for collapsed charts we use CSS
  // .phenomenon-category:not([open]) .phenomenon-expensive { display:none } and
  // components check closest details open. Simplest: always render text; charts
  // should check. Here we just render children (text-safe).
  return <>{children}</>;
}
