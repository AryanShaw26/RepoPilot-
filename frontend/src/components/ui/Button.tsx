import { forwardRef, type ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "default" | "small" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-ink border-accent hover:bg-accent-strong",
  secondary: "bg-well text-ink border-edge hover:bg-surface-raised",
  ghost: "bg-transparent text-ink-muted border-transparent hover:bg-well hover:text-ink",
  danger: "bg-led-red/10 text-led-red border-led-red/40 hover:bg-led-red/20",
};

const sizes: Record<ButtonSize, string> = {
  default: "min-h-11 px-4 py-2",
  small: "min-h-9 px-3 py-1.5",
  icon: "size-11 p-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant = "secondary", size = "default", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={`key inline-flex items-center justify-center gap-2 rounded-md border font-mono text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  )
);

Button.displayName = "Button";
