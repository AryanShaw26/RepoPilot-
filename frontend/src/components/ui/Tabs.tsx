import { useState } from "react";

export interface TabDefinition {
  id: string;
  label: string;
  content: React.ReactNode;
}

interface TabsProps {
  tabs: TabDefinition[];
  initialTab?: string;
  label: string;
}

export function Tabs({ tabs, initialTab, label }: TabsProps) {
  const [active, setActive] = useState(initialTab ?? tabs[0]?.id ?? "");
  const current = tabs.find((tab) => tab.id === active);

  return (
    <div>
      <div role="tablist" aria-label={label} className="flex gap-1 border-b border-edge">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            onClick={() => setActive(tab.id)}
            className={`min-h-11 border-b-2 px-4 font-mono text-sm ${
              active === tab.id
                ? "border-accent text-ink"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {current && (
        <section
          id={`panel-${current.id}`}
          role="tabpanel"
          aria-labelledby={`tab-${current.id}`}
          className="pt-4"
        >
          {current.content}
        </section>
      )}
    </div>
  );
}
