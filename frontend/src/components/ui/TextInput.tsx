import React from "react";
import { Led } from "./Led";

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  ledStatus?: "idle" | "checking" | "valid" | "error";
  leftElement?: React.ReactNode;
  rightElement?: React.ReactNode;
}

export const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(
  (
    {
      label,
      helperText,
      error,
      ledStatus,
      leftElement,
      rightElement,
      disabled,
      className = '',
      id,
      ...props
    },
    ref
  ) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    const getLedStatus = (): "green" | "amber" | "red" | "off" => {
      switch (ledStatus) {
        case "checking":
          return 'amber';
        case "valid":
          return 'green';
        case "error":
          return 'red';
        case "idle":
        default:
          return 'off';
      }
    };

    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <div className="flex items-center justify-between">
            <label
              htmlFor={inputId}
              className="flex items-center gap-2 font-mono text-xs font-medium uppercase tracking-wider text-ink-muted"
            >
              {label}
            </label>
            {ledStatus && (
              <div className="flex items-center gap-1.5">
                <Led
                  status={getLedStatus()}
                  pulse={ledStatus === 'checking'}
                  size="sm"
                />
                <span className="font-mono text-[10px] uppercase text-ink-muted">
                  {ledStatus}
                </span>
              </div>
            )}
          </div>
        )}

        <div className="relative flex w-full items-center">
          {leftElement && (
            <div className="pointer-events-none absolute left-3 flex items-center text-ink-muted">
              {leftElement}
            </div>
          )}

          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? `${inputId}-error` : helperText ? `${inputId}-help` : undefined}
            className={`min-h-11 w-full rounded-md border bg-surface-inset px-3.5 py-2 font-mono text-sm text-ink shadow-inset placeholder:text-ink-faint focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus/30 disabled:cursor-not-allowed disabled:opacity-50 ${
              error ? "border-led-red focus:border-led-red focus:ring-led-red/30" : "border-edge"
            } ${leftElement ? "pl-9" : ""} ${rightElement ? "pr-9" : ""} ${className}`}
            {...props}
          />

          {rightElement && (
            <div className="absolute right-3 flex items-center text-ink-muted">
              {rightElement}
            </div>
          )}
        </div>

        {error ? (
          <p id={`${inputId}-error`} className="mt-0.5 font-mono text-[11px] text-led-red">{error}</p>
        ) : helperText ? (
          <p id={`${inputId}-help`} className="mt-0.5 font-mono text-[11px] text-ink-muted">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

TextInput.displayName = 'TextInput';
