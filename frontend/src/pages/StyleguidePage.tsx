import { Check, Search, Settings, X } from "lucide-react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { IconKey } from "../components/ui/IconKey";
import { Led } from "../components/ui/Led";
import { Panel } from "../components/ui/Panel";
import { Placard } from "../components/ui/Placard";
import { Segmented } from "../components/ui/Segmented";
import { Statement } from "../components/ui/Statement";
import { Switch } from "../components/ui/Switch";
import { TextArea } from "../components/ui/TextArea";
import { TextInput } from "../components/ui/TextInput";
import { PageHeading, TrustNote } from "./shared";
import { useState } from "react";

export function StyleguidePage() {
  const [mode, setMode] = useState<"fact" | "hypothesis">("fact");
  const [enabled, setEnabled] = useState(false);

  return (
    <div>
      <PageHeading
        eyebrow="System reference"
        title="Styleguide"
        description="Design tokens, controls, status indicators, and trust labels used throughout RepoPilot."
      />
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel header={<h2 className="font-display text-xl">Surfaces & controls</h2>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-edge bg-surface-raised p-4 shadow-e1">
              <p className="font-mono text-xs">Raised surface</p><p className="mt-1 text-xs text-ink-muted">surface-raised · elev-1</p>
            </div>
            <div className="rounded-md border border-edge bg-surface-inset p-4 shadow-inset">
              <p className="font-mono text-xs">Inset surface</p><p className="mt-1 text-xs text-ink-muted">surface-inset · inset-1</p>
            </div>
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button variant="primary">Primary key</Button>
              <Button variant="secondary">Secondary key</Button>
              <Button variant="ghost">Ghost key</Button>
              <Button variant="danger"><X className="size-4" /> Destructive</Button>
              <IconKey label="Search"><Search className="size-4" /></IconKey>
              <IconKey label="Settings"><Settings className="size-4" /></IconKey>
            </div>
            <TextInput label="Text input" placeholder="Type here" helperText="Helper text" />
            <TextInput label="Valid input" defaultValue="Verified value" ledStatus="valid" />
            <div className="sm:col-span-2"><TextArea label="Multiline input" placeholder="Add context…" /></div>
            <div className="flex flex-wrap items-center gap-3">
              <Switch checked={enabled} onChange={setEnabled} label="Example switch" />
              <Segmented
                label="Statement type example"
                value={mode}
                onChange={setMode}
                options={[
                  { value: "fact", label: "Fact" },
                  { value: "hypothesis", label: "Hypothesis" },
                ]}
              />
            </div>
          </div>
        </Panel>

        <Panel header={<h2 className="font-display text-xl">Status & trust</h2>}>
          <div className="flex flex-wrap gap-2">
            <Badge tone="green"><Check className="size-3" /> Ready</Badge>
            <Badge tone="amber"><Led status="amber" /> Processing</Badge>
            <Badge tone="red"><Led status="red" /> Failed</Badge>
            <Badge tone="blue">Indexed</Badge>
            <Badge>Neutral</Badge>
          </div>
          <div className="mt-4 grid gap-2">
            <Statement text="Source path and line range were returned by the repository index." kind="fact" />
            <Statement text="The report may be caused by an unhandled boundary condition." kind="hypothesis" />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Led status="green" /><Led status="amber" pulse /><Led status="red" /><Led status="blue" /><Led status="off" />
            <span className="font-mono text-xs text-ink-muted">Indicator colors are paired with visible labels in product screens.</span>
          </div>
          <TrustNote>Evidence is a repository fact; generated interpretation remains a hypothesis.</TrustNote>
          <Placard title="Module label" subtitle="Brushed metal placard" serial="RP-01" className="mt-4" />
        </Panel>

        <Panel header={<h2 className="font-display text-xl">Panel variants</h2>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Panel variant="raised"><p className="font-mono text-xs">Raised panel</p></Panel>
            <Panel variant="sunken"><p className="font-mono text-xs">Sunken panel</p></Panel>
            <Panel variant="flat"><p className="font-mono text-xs">Flat panel</p></Panel>
            <Panel variant="instrument"><p className="font-mono text-xs">Instrument panel</p></Panel>
          </div>
        </Panel>

        <Panel header={<h2 className="font-display text-xl">Empty state</h2>}>
          <EmptyState title="No data" description="An empty state explains what is missing and how to continue." />
        </Panel>
      </div>
    </div>
  );
}
