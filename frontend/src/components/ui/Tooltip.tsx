import type { ReactNode } from "react";

interface TooltipProps {
  content: string;
  children: ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-max max-w-64 -translate-x-1/2 rounded border border-edge bg-surface-raised px-2 py-1 font-mono text-xs text-ink shadow-e2 group-hover:block group-focus-within:block"
      >
        {content}
      </span>
    </span>
  );
}
