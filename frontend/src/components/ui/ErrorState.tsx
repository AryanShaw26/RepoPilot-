import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";

interface ErrorStateProps {
  title: string;
  message: string;
  code?: string;
  onRetry?: () => void;
}

export function ErrorState({ title, message, code, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="rounded-md border border-led-red/50 bg-surface-raised p-5 text-ink">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-led-red" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-lg">{title}</h3>
          <p className="mt-1 break-words text-sm text-ink-muted">{message}</p>
          {code && <code className="mt-2 inline-block text-xs text-led-red">{code}</code>}
          {onRetry && (
            <div className="mt-4">
              <Button onClick={onRetry}>Retry</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
