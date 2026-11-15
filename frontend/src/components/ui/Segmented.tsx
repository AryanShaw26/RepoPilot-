import type { KeyboardEvent } from "react";

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedProps<T extends string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  className = "",
}: SegmentedProps<T>) {
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentIndex = options.findIndex((option) => option.value === value);
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = options[(currentIndex + delta + options.length) % options.length];
    onChange(next.value);
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={handleKeyDown}
      className={`inline-flex flex-wrap gap-1 rounded-md border border-edge bg-surface-inset p-1 ${className}`}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          tabIndex={value === option.value ? 0 : -1}
          onClick={() => onChange(option.value)}
          className={`min-h-9 rounded px-3 font-mono text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${
            value === option.value ? "bg-surface-raised text-ink shadow-e1" : "text-ink-muted hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
