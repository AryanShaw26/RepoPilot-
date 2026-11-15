import { Badge } from "./Badge";

export interface StatementProps {
  text: string;
  kind: "fact" | "hypothesis";
  className?: string;
}

export function Statement({ text, kind, className = "" }: StatementProps) {
  const isFact = kind === "fact";
  return (
    <span className={`inline-flex flex-wrap items-baseline gap-2 ${className}`}>
      <Badge tone={isFact ? "green" : "amber"}>
        <span aria-hidden="true">{isFact ? "✓" : "?"}</span>
        {isFact ? "Verified" : "Hypothesis"}
      </Badge>
      <span>{text}</span>
    </span>
  );
}
