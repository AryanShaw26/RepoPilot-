import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileCheck2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { exportPlanMarkdown, getPlan } from "../api/plans";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Panel } from "../components/ui/Panel";
import { Statement } from "../components/ui/Statement";
import { presentApiError } from "../utils/apiErrors";
import { LoadingState, PageHeading, QueryError, TrustNote } from "./shared";

export function PlanPage() {
  const { repositoryId = "", planId = "" } = useParams();
  const plan = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => getPlan(planId),
    enabled: Boolean(planId),
  });
  const exportPlan = useMutation({
    mutationFn: () => exportPlanMarkdown(planId),
    onSuccess: (markdown) => {
      const file = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "repopilot-plan.md";
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  if (plan.isPending) return <LoadingState label="Loading contribution plan…" />;
  if (plan.isError) return <QueryError error={plan.error} onRetry={() => void plan.refetch()} />;
  const content = plan.data.plan;

  return (
    <div>
      <PageHeading
        eyebrow="Contribution plan"
        title="Implementation plan"
        description="A structured proposal; hypotheses and risks are clearly identified."
        actions={
          <>
            <Link to={`/repositories/${repositoryId}/investigations/${plan.data.investigation_id}`}>
              <Button variant="ghost">Back to investigation</Button>
            </Link>
            <Button variant="primary" disabled={exportPlan.isPending} onClick={() => exportPlan.mutate()}>
              <Download className="size-4" /> {exportPlan.isPending ? "Exporting…" : "Export Markdown"}
            </Button>
          </>
        }
      />
      {exportPlan.isError && (
        <div className="mb-4"><QueryError error={exportPlan.error} /></div>
      )}
      <Panel variant="instrument" className="mb-5">
        <div className="flex items-start gap-3">
          <FileCheck2 className="mt-1 size-5 shrink-0 text-led-green" aria-hidden="true" />
          <div>
            <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-glass-ink/70">Plan summary · AI-generated</p>
            <Statement text={content.summary.text} kind="hypothesis" className="text-sm text-glass-ink" />
          </div>
        </div>
      </Panel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
        <div className="space-y-5">
          <Panel header={<h2 className="font-display text-xl">Implementation steps</h2>}>
            {content.steps.length ? (
              <ol className="space-y-4">
                {content.steps.map((step) => (
                  <li key={`${step.order}-${step.title}`} className="relative rounded-md border border-edge bg-surface-inset p-4">
                    <div className="flex items-start gap-3">
                      <span className="grid size-8 shrink-0 place-items-center rounded-full border border-edge bg-surface-raised font-mono text-sm">{step.order}</span>
                      <div className="min-w-0">
                        <h3 className="font-display text-lg">
                          <Statement text={step.title} kind={step.kind === "fact" ? "fact" : "hypothesis"} />
                        </h3>
                        <div className="mt-1 text-sm"><Statement text={step.description} kind={step.kind === "fact" ? "fact" : "hypothesis"} /></div>
                        {step.files.length > 0 && (
                          <ul className="mt-3 space-y-1">
                            {step.files.map((path) => (
                              <li key={path}>
                                <Link
                                  to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(path)}`}
                                  className="break-all font-mono text-xs text-accent underline"
                                >
                                  {path} · Verified
                                </Link>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState title="No steps returned" description="This plan did not include implementation steps." />
            )}
          </Panel>

          <Panel header={<h2 className="font-display text-xl">Validation checklist</h2>}>
            <ul className="space-y-3">
              {content.validation_checklist.map((item, index) => (
                <li key={`${index}-${item}`} className="flex items-start gap-2">
                  <span className="mt-1 size-4 shrink-0 rounded border border-edge bg-surface-inset" aria-hidden="true" />
                  <Statement text={item} kind="hypothesis" className="text-sm" />
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <aside className="space-y-5">
          <Panel header={<div className="flex items-center justify-between gap-2"><h2 className="font-display text-xl">Impacted files</h2><Badge tone="green">{content.impacted_files.length} · Verified</Badge></div>}>
            {content.impacted_files.length ? (
              <ul className="space-y-3">
                {content.impacted_files.map((file) => (
                  <li key={file.path} className="border-b border-edge pb-3 last:border-0">
                    <Link to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(file.path)}`} className="break-all font-mono text-xs text-accent underline">{file.path}</Link>
                    <p className="mt-1 text-xs"><Statement text={file.reason} kind="fact" /></p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-muted">No impacted files were listed.</p>
            )}
          </Panel>

          <Panel header={<div className="flex items-center justify-between gap-2"><h2 className="font-display text-xl">Risks</h2><Badge tone="amber">Hypotheses</Badge></div>}>
            {content.risks.length ? (
              <ul className="space-y-3">
                {content.risks.map((risk, index) => (
                  <li key={`${index}-${risk.text}`} className="rounded border border-led-amber/40 bg-surface-inset p-3">
                    <Statement text={risk.text} kind="hypothesis" />
                    <p className="mt-2 font-mono text-[10px] text-ink-muted">Confidence: {risk.confidence}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-muted">No risks were reported.</p>
            )}
          </Panel>

          <Panel header={<h2 className="font-display text-xl">Tests</h2>}>
            {content.tests.existing.length + content.tests.recommended.length > 0 ? (
              <div className="space-y-4">
                {content.tests.existing.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-mono text-[10px] uppercase text-ink-muted">Existing tests</h3>
                    <ul className="space-y-2">
                      {content.tests.existing.map((test, index) => (
                        <li key={`${test.path}-${index}`} className="text-xs">
                          <Link to={`/repositories/${repositoryId}/explorer?path=${encodeURIComponent(test.path)}`} className="break-all text-accent underline">{test.path}</Link>
                          <p className="text-ink-muted">{test.method} · {test.confidence} · Verified</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {content.tests.recommended.length > 0 && (
                  <div>
                    <h3 className="mb-2 font-mono text-[10px] uppercase text-ink-muted">Recommended</h3>
                    <ul className="space-y-2">
                      {content.tests.recommended.map((test, index) => (
                        <li key={`${test.scenario}-${index}`} className="text-xs"><Statement text={test.scenario} kind="hypothesis" /></li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-ink-muted">No test information was returned.</p>
            )}
          </Panel>
          <TrustNote>{content.disclaimer || plan.data.disclaimer}</TrustNote>
        </aside>
      </div>
    </div>
  );
}
