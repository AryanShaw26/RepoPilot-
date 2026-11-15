import type { ReactNode } from "react";

export interface PlacardProps {
  title: string;
  subtitle?: string;
  serial?: string;
  className?: string;
  children?: ReactNode;
}

export const Placard: React.FC<PlacardProps> = ({
  title,
  subtitle,
  serial,
  className = '',
  children,
}) => {
  return (
    <div className={`placard relative select-none p-3.5 ${className}`}>
      <span className="screw absolute left-1.5 top-1.5" aria-hidden="true" />
      <span className="screw absolute right-1.5 top-1.5" aria-hidden="true" />
      <span className="screw absolute bottom-1.5 left-1.5" aria-hidden="true" />
      <span className="screw absolute bottom-1.5 right-1.5" aria-hidden="true" />
      <div className="flex items-center justify-between px-3">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h3 className="font-mono text-xs font-bold uppercase tracking-widest text-ink-muted">
              {title}
            </h3>
            {serial && (
              <span className="rounded border border-edge bg-surface-inset px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                SN: {serial}
              </span>
            )}
          </div>
          {subtitle && <p className="mt-0.5 font-mono text-[11px] text-ink-muted">{subtitle}</p>}
        </div>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>
    </div>
  );
};
