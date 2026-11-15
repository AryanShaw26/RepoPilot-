import { Badge } from "./Badge";
import { Led } from "./Led";
import type { AnalysisStage } from "../../types";

interface StatWellProps {
  label: string;
  value: string | number;
}

export function StatWell({ label, value }: StatWellProps) {
  return (
    <div className="rounded-md border border-edge bg-surface-inset p-4 shadow-inset">
      <p className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">{label}</p>
      <p className="mt-1 font-display text-2xl tabular-nums text-ink">{value}</p>
      <Badge tone="green" className="mt-2">Verified</Badge>
    </div>
  );
}

interface NeedleGaugeProps {
  value: number;
  label: string;
}

export function NeedleGauge({ value, label }: NeedleGaugeProps) {
  const bounded = Math.max(0, Math.min(100, value));
  const angle = -90 + bounded * 1.8;
  return (
    <div className="flex flex-col items-center rounded-md border border-edge bg-surface-inset p-3 shadow-inset">
      <svg viewBox="0 0 160 100" className="w-full max-w-48" role="img" aria-label={`${label}: ${bounded}%`}>
        <path d="M 10 90 A 70 70 0 0 1 150 90" fill="none" stroke="var(--edge)" strokeWidth="10" strokeLinecap="round" />
        <path d="M 10 90 A 70 70 0 0 1 150 90" fill="none" stroke="var(--led-green)" strokeWidth="10" strokeLinecap="round" pathLength="100" strokeDasharray={`${bounded} 100`} />
        <line x1="80" y1="90" x2="80" y2="27" stroke="var(--brand)" strokeWidth="3" strokeLinecap="round" transform={`rotate(${angle} 80 90)`} />
        <circle cx="80" cy="90" r="6" fill="var(--metal-lo)" stroke="var(--edge)" />
      </svg>
      <p className="font-mono text-xs uppercase text-ink-muted">{label}</p>
      <p className="font-display text-xl tabular-nums">{bounded}%</p>
      <Badge tone="green">Verified</Badge>
    </div>
  );
}

interface CounterDrumProps {
  value: number | null;
  label: string;
}

export function CounterDrum({ value, label }: CounterDrumProps) {
  return (
    <div className="rounded-md border border-edge bg-glass px-4 py-3 text-center text-glass-ink shadow-inset">
      <p className="font-mono text-[10px] uppercase tracking-wider text-glass-ink/70">{label}</p>
      <p className="mt-1 font-mono text-3xl tabular-nums">{value === null ? "----" : String(value).padStart(4, "0")}</p>
      <p className="mt-1 text-xs text-glass-ink/70">{value === null ? "count unavailable while indexing" : "Verified file count"}</p>
    </div>
  );
}

const stages: AnalysisStage[] = ["queued", "fetching", "parsing", "indexing", "embedding", "ready"];
const stageLabels: Record<AnalysisStage, string> = {
  queued: "Queued",
  fetching: "Fetch",
  parsing: "Parse",
  indexing: "Index",
  embedding: "Embed",
  ready: "Ready",
  failed: "Failed",
};

interface StageLampsProps {
  stage: AnalysisStage;
  semanticAvailable?: boolean;
}

export function StageLamps({ stage, semanticAvailable = true }: StageLampsProps) {
  const currentIndex = stages.indexOf(stage);
  return (
    <ol aria-label="Analysis stages" className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {stages.map((item, index) => {
        const complete = stage === "ready" || (currentIndex >= 0 && index < currentIndex);
        const current = item === stage;
        const unavailable = item === "embedding" && !semanticAvailable;
        const status = stage === "failed" && current
          ? "red"
          : complete
            ? "green"
            : current
              ? "amber"
              : "off";
        return (
          <li key={item} className="flex items-center gap-2 font-mono text-xs text-ink-muted">
            <Led status={unavailable ? "off" : status} pulse={current && !unavailable} />
            <span>{stageLabels[item]}{unavailable ? " (unavailable)" : complete ? " · Verified" : current ? " · Live" : ""}</span>
          </li>
        );
      })}
      {stage === "failed" && (
        <li className="flex items-center gap-2 font-mono text-xs text-led-red">
          <Led status="red" />
          <span>Failed · Verified</span>
        </li>
      )}
    </ol>
  );
}

interface EvidenceMeterProps {
  strength: "weak" | "moderate" | "strong";
  count: number;
}

export function EvidenceMeter({ strength, count }: EvidenceMeterProps) {
  const levels = { weak: 1, moderate: 2, strong: 3 };
  const value = levels[strength];
  return (
    <div className="rounded-md border border-edge bg-surface-inset p-4 shadow-inset">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-xs uppercase tracking-wider text-ink-muted">Evidence strength · Verified</p>
        <Badge tone={strength === "strong" ? "green" : strength === "moderate" ? "amber" : "red"}>{strength}</Badge>
      </div>
      <div className="mt-3 flex gap-1" role="img" aria-label={`${strength} evidence strength`}>
        {[1, 2, 3].map((level) => (
          <span key={level} className={`h-2 flex-1 rounded-full ${level <= value ? "bg-led-green" : "bg-edge"}`} />
        ))}
      </div>
      <p className="mt-3 text-xs text-ink-muted">{count} evidence result{count === 1 ? "" : "s"} · Verified</p>
    </div>
  );
}
