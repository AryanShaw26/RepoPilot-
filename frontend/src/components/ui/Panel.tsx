import { forwardRef, type HTMLAttributes, type ReactNode } from "react";

export interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "raised" | "sunken" | "flat" | "instrument";
  header?: ReactNode;
  footer?: ReactNode;
  borderGlow?: "none" | "amber" | "green" | "blue";
}

const variants = {
  raised: "panel-raised",
  sunken: "panel-sunken",
  flat: "bg-surface-raised border border-edge",
  instrument: "panel-instrument",
};

const glows = {
  none: "",
  amber: "border-led-amber/60 shadow-[0_0_15px] shadow-led-amber/10",
  green: "border-led-green/60 shadow-[0_0_15px] shadow-led-green/10",
  blue: "border-led-blue/60 shadow-[0_0_15px] shadow-led-blue/10",
};

export const Panel = forwardRef<HTMLDivElement, PanelProps>(
  (
    {
      variant = "raised",
      header,
      footer,
      borderGlow = "none",
      className = "",
      children,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      className={`overflow-hidden rounded-lg border-edge transition-colors ${variants[variant]} ${glows[borderGlow]} ${className}`}
      {...props}
    >
      {header && (
        <div className="flex items-center justify-between border-b border-edge bg-surface-raised/60 px-4 py-3">
          {header}
        </div>
      )}
      <div className="p-4">{children}</div>
      {footer && (
        <div className="flex items-center justify-between border-t border-edge bg-surface-raised/40 px-4 py-2.5">
          {footer}
        </div>
      )}
    </div>
  )
);

Panel.displayName = "Panel";
