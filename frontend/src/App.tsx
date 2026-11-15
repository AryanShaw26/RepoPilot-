import { lazy, Suspense, useState } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  Cable,
  Compass,
  FileSearch,
  Home,
  Search,
  ShieldCheck,
  TestTube2,
} from "lucide-react";
import { BrowserRouter, Link, NavLink, Navigate, Outlet, Route, Routes, useParams } from "react-router-dom";
import { getHealth } from "./api/health";
import { useTheme, ThemeProvider } from "./context/ThemeContext";
import { Badge } from "./components/ui/Badge";
import { Switch } from "./components/ui/Switch";

const LandingPage = lazy(() => import("./pages/LandingPage").then((module) => ({ default: module.LandingPage })));
const AnalysisPage = lazy(() => import("./pages/AnalysisPage").then((module) => ({ default: module.AnalysisPage })));
const OverviewPage = lazy(() => import("./pages/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const ExplorerPage = lazy(() => import("./pages/ExplorerPage").then((module) => ({ default: module.ExplorerPage })));
const SearchPage = lazy(() => import("./pages/SearchPage").then((module) => ({ default: module.SearchPage })));
const GraphPage = lazy(() => import("./pages/GraphPage").then((module) => ({ default: module.GraphPage })));
const IssuesPage = lazy(() => import("./pages/IssuesPage").then((module) => ({ default: module.IssuesPage })));
const TestsPage = lazy(() => import("./pages/TestsPage").then((module) => ({ default: module.TestsPage })));
const InvestigationPage = lazy(() => import("./pages/InvestigationPage").then((module) => ({ default: module.InvestigationPage })));
const PlanPage = lazy(() => import("./pages/PlanPage").then((module) => ({ default: module.PlanPage })));
const StyleguidePage = lazy(() => import("./pages/StyleguidePage").then((module) => ({ default: module.StyleguidePage })));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 15_000,
      },
    },
  });
}

const navItems = [
  { label: "Overview", path: "", icon: Home },
  { label: "Explorer", path: "/explorer", icon: Compass },
  { label: "Search", path: "/search", icon: Search },
  { label: "Dependencies", path: "/graph", icon: Cable },
  { label: "Issues", path: "/issues", icon: FileSearch },
  { label: "Tests", path: "/tests", icon: TestTube2 },
];

function AppShell() {
  const { repositoryId } = useParams();
  const { theme, setTheme } = useTheme();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15_000,
  });
  const ready = health.data?.db && health.data.migrated;

  return (
    <div className="min-h-screen bg-surface text-ink">
      <header className="sticky top-0 z-40 border-b border-edge bg-surface-raised/95 shadow-e1 backdrop-blur">
        <div className="mx-auto flex min-h-16 max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-3 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus">
            <span className="grid size-9 place-items-center rounded-md border border-edge bg-surface-inset text-accent shadow-inset" aria-hidden="true">
              <Boxes className="size-5" />
            </span>
            <span>
              <span className="block font-display text-xl font-bold tracking-wide">RepoPilot</span>
              <span className="hidden font-mono text-[10px] uppercase tracking-widest text-ink-muted sm:block">Repository intelligence</span>
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block">
              {health.isError ? (
                <Badge tone="red"><Activity className="size-3" /> Backend offline</Badge>
              ) : ready ? (
                <Badge tone="green"><ShieldCheck className="size-3" /> API ready · Verified</Badge>
              ) : (
                <Badge tone="amber"><Activity className="size-3" /> Checking API</Badge>
              )}
            </div>
            <Switch
              checked={theme === "dark"}
              onChange={(checked) => setTheme(checked ? "dark" : "light")}
              label={theme === "dark" ? "Dark theme" : "Light theme"}
            />
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px]">
        {repositoryId && (
          <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-56 shrink-0 border-r border-edge bg-surface-raised/60 p-4 lg:block">
            <p className="mb-3 px-3 font-mono text-[10px] uppercase tracking-widest text-ink-muted">Workspace</p>
            <nav aria-label="Repository navigation" className="space-y-1">
              {navItems.map(({ label, path, icon: Icon }) => (
                <NavLink
                  key={label}
                  to={`/repositories/${repositoryId}${path}`}
                  end={path === ""}
                  className={({ isActive }) =>
                    `flex min-h-11 items-center gap-3 rounded-md px-3 font-mono text-xs transition-colors ${
                      isActive ? "bg-accent/10 text-ink shadow-inset" : "text-ink-muted hover:bg-surface-raised hover:text-ink"
                    }`
                  }
                >
                  <Icon className="size-4" aria-hidden="true" />
                  {label}
                </NavLink>
              ))}
            </nav>
          </aside>
        )}

        <main className="min-w-0 flex-1">
          {repositoryId && (
            <nav aria-label="Repository navigation" className="flex gap-1 overflow-x-auto border-b border-edge px-3 py-2 lg:hidden">
              {navItems.map(({ label, path }) => (
                <NavLink
                  key={label}
                  to={`/repositories/${repositoryId}${path}`}
                  end={path === ""}
                  className={({ isActive }) =>
                    `min-h-11 shrink-0 rounded px-3 py-2 font-mono text-xs ${
                      isActive ? "bg-accent/10 text-ink" : "text-ink-muted"
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="mx-auto w-full max-w-[1400px] p-4 sm:p-6 lg:p-8">
            <Suspense fallback={<div role="status" className="flex min-h-48 items-center justify-center font-mono text-sm text-ink-muted">Loading view…</div>}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<LandingPage />} />
        <Route path="repositories/:repositoryId/analysis" element={<AnalysisPage />} />
        <Route path="repositories/:repositoryId" element={<OverviewPage />} />
        <Route path="repositories/:repositoryId/explorer" element={<ExplorerPage />} />
        <Route path="repositories/:repositoryId/search" element={<SearchPage />} />
        <Route path="repositories/:repositoryId/graph" element={<GraphPage />} />
        <Route path="repositories/:repositoryId/issues" element={<IssuesPage />} />
        <Route path="repositories/:repositoryId/tests" element={<TestsPage />} />
        <Route path="repositories/:repositoryId/investigations/:investigationId" element={<InvestigationPage />} />
        <Route path="repositories/:repositoryId/plans/:planId" element={<PlanPage />} />
        <Route path="styleguide" element={<StyleguidePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
