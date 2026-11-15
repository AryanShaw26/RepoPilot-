import { forwardRef, type HTMLAttributes } from "react";

export interface LedProps extends HTMLAttributes<HTMLSpanElement> {
  status: "green" | "amber" | "red" | "blue" | "off";
  size?: "sm" | "md" | "lg";
  pulse?: boolean;
}

const sizes = {
  sm: "size-2",
  md: "size-3",
  lg: "size-4",
};

const statuses = {
  green: "bg-led-green shadow-[0_0_7px] shadow-led-green/70",
  amber: "bg-led-amber shadow-[0_0_7px] shadow-led-amber/70",
  red: "bg-led-red shadow-[0_0_7px] shadow-led-red/70",
  blue: "bg-led-blue shadow-[0_0_7px] shadow-led-blue/70",
  off: "bg-ink-faint",
};

export const Led = forwardRef<HTMLSpanElement, LedProps>(
  ({ status, size = "md", className = "", pulse = false, ...props }, ref) => (
    <span
      ref={ref}
      className={`inline-block shrink-0 rounded-full ${sizes[size]} ${statuses[status]} ${pulse ? "animate-pulse" : ""} ${className}`}
      aria-hidden="true"
      {...props}
    />
  )
);

Led.displayName = "Led";
