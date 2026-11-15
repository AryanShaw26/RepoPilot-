import React from "react";

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helperText?: string;
  error?: string;
}

export const TextArea = React.forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, helperText, error, disabled, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="font-mono text-xs font-medium uppercase tracking-wider text-ink-muted"
          >
            {label}
          </label>
        )}

        <textarea
          ref={ref}
          id={inputId}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${inputId}-error` : helperText ? `${inputId}-help` : undefined}
          className={`min-h-24 w-full resize-y rounded-md border bg-surface-inset px-3.5 py-2.5 font-mono text-sm text-ink shadow-inset placeholder:text-ink-faint focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus/30 disabled:cursor-not-allowed disabled:opacity-50 ${
            error ? "border-led-red focus:border-led-red focus:ring-led-red/30" : "border-edge"
          } ${className}`}
          {...props}
        />

        {error ? (
          <p id={`${inputId}-error`} className="mt-0.5 font-mono text-[11px] text-led-red">{error}</p>
        ) : helperText ? (
          <p id={`${inputId}-help`} className="mt-0.5 font-mono text-[11px] text-ink-muted">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

TextArea.displayName = 'TextArea';
