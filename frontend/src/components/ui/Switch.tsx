import { forwardRef, type ButtonHTMLAttributes } from "react";

export interface SwitchProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked, onChange, label, className = "", ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`inline-flex min-h-11 items-center gap-2 rounded-md px-2 font-mono text-xs text-ink-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${className}`}
      {...props}
    >
      <span className={`relative h-5 w-9 rounded-pill border border-edge transition-colors ${checked ? "bg-accent" : "bg-surface-inset"}`}>
        <span className={`absolute top-0.5 size-3.5 rounded-full bg-accent-ink shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0.5"}`} />
      </span>
      <span>{label}</span>
    </button>
  )
);

Switch.displayName = "Switch";
