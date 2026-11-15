import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-3 p-6 text-center">
      {icon && <div className="text-ink-muted" aria-hidden="true">{icon}</div>}
      <h3 className="font-display text-xl text-ink">{title}</h3>
      <p className="max-w-lg text-sm text-ink-muted">{description}</p>
      {action}
    </div>
  );
}
