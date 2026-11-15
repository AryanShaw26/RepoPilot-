import { forwardRef, type HTMLAttributes } from "react";

type BadgeTone = "neutral" | "green" | "amber" | "red" | "blue";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

const tones: Record<BadgeTone, string> = {
  neutral: "border-edge bg-well text-ink-muted",
  green: "border-led-green/50 bg-led-green/10 text-led-green",
  amber: "border-led-amber/50 bg-led-amber/10 text-led-amber",
  red: "border-led-red/50 bg-led-red/10 text-led-red",
  blue: "border-led-blue/50 bg-led-blue/10 text-led-blue",
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className = "", tone = "neutral", ...props }, ref) => (
    <span
      ref={ref}
      className={`inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 font-mono text-xs ${tones[tone]} ${className}`}
      {...props}
    />
  )
);

Badge.displayName = "Badge";
