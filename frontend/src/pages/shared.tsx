import { AlertCircle, LoaderCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ErrorState } from "../components/ui/ErrorState";
import { Panel } from "../components/ui/Panel";
import { presentApiError } from "../utils/apiErrors";

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 border-b border-edge pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">{eyebrow}</p>
        <h1 className="font-display text-3xl font-semibold sm:text-4xl">{title}</h1>
        {description && <p className="mt-2 max-w-3xl text-sm text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function LoadingState({ label = "Loading repository data" }: { label?: string }) {
  return (
    <div role="status" className="flex min-h-48 items-center justify-center gap-3 text-ink-muted">
      <LoaderCircle className="size-5 animate-spin text-accent" aria-hidden="true" />
      <span className="font-mono text-sm">{label}</span>
    </div>
  );
}

export function QueryError({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const presented = presentApiError(error);
  return (
    <ErrorState
      title={presented.title}
      message={presented.message}
      code={presented.code}
      onRetry={onRetry}
    />
  );
}

export function TrustNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-edge bg-surface-raised px-3 py-2 text-xs text-ink-muted">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone = status === "ready" ? "green" : status === "failed" ? "red" : "amber";
  return <Badge tone={tone}>{status} · Verified</Badge>;
}

export function NotFound({ resource }: { resource: string }) {
  return (
    <Panel>
      <div className="py-8 text-center">
        <h2 className="font-display text-2xl">{resource} not found</h2>
        <p className="mt-2 text-sm text-ink-muted">The item may have been removed or belongs to a different session.</p>
        <Link to="/" className="mt-4 inline-block">
          <Button>Return to repositories</Button>
        </Link>
      </div>
    </Panel>
  );
}
