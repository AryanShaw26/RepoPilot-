interface SkeletonProps {
  className?: string;
  label?: string;
}

export function Skeleton({ className = "", label = "Loading" }: SkeletonProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`skeleton-shimmer inline-block rounded-md ${className}`}
    />
  );
}
