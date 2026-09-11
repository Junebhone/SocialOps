"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api, type AgentTotals, type Brand, type QueueStats } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/inbox", label: "Inbox", icon: NavInbox },
  { href: "/content", label: "Content", icon: NavContent },
  { href: "/ideas", label: "Ideas", icon: NavIdeas },
  { href: "/insights", label: "Insights", icon: NavInsights },
  { href: "/agents", label: "Agents", icon: NavAgents },
];

// The two orchestrator graphs (worker/orchestrator.py), shown literally —
// the sidebar names the actual pipeline, not a marketing abstraction of it.
// Only the nodes that call a model are highlighted; ingest/persist are plain.
const PIPELINES = [
  { label: "comment", nodes: ["ingest", "triage", "response", "persist"], model: [1, 2] },
  { label: "asset", nodes: ["ingest", "media", "content", "persist"], model: [1, 2] },
];

// The full agent roster, fixed — shown whether or not each one has run yet.
// `agent_runs` totals only return rows for agents that have actually been
// invoked, which used to mean this section was empty (or missing agents) on
// a fresh brand; a sidebar that only sometimes has content reads as broken.
const ALL_AGENTS = ["triage", "response", "content", "media", "ideation", "insight"] as const;

// One color per brand so the sidebar dot and dropdown stay legible with more
// than one brand seeded — cycles through the existing status/accent tokens
// rather than inventing new ones.
const BRAND_HUES = ["var(--primary)", "var(--status-good)", "var(--status-warn)"];

/**
 * Left sidebar, top bar with a brand selector and live queue stats.
 *
 * `brand_id` lives in the URL, never in a session (D17). The API is stateless,
 * so a link someone pastes into Slack has to resolve to the same view they were
 * looking at.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const params = useSearchParams();
  const brandId = params.get("brand_id");

  const [brands, setBrands] = useState<Brand[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [totals, setTotals] = useState<AgentTotals[] | null>(null);
  const [brandOpen, setBrandOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .brands()
      .then((rows) => {
        if (!cancelled) setBrands(rows);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!brandId && brands && brands.length > 0) {
      router.replace(`${pathname}?brand_id=${brands[0].id}`);
    }
  }, [brandId, brands, pathname, router]);

  // Agent activity bars: real per-agent run counts, refreshed slowly — this is
  // sidebar chrome, not a page a reviewer is watching drain in real time.
  useEffect(() => {
    if (!brandId) return;
    let cancelled = false;
    const load = () =>
      api
        .agentRuns(Number(brandId))
        .then((page) => {
          if (!cancelled) setTotals(page.totals);
        })
        .catch(() => {
          /* sidebar chrome — a dropped poll here is not worth surfacing */
        });
    load();
    const timer = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [brandId]);

  const brandIndex = brands?.findIndex((b) => String(b.id) === brandId) ?? -1;
  const currentBrand = brandIndex >= 0 ? brands![brandIndex] : null;

  // Always the full roster, real counts merged in where they exist. This is
  // what keeps the section a fixed height instead of shrinking to whatever
  // subset of agents happened to have run.
  const byAgent = new Map((totals ?? []).map((t) => [t.agent, t]));
  const activity = ALL_AGENTS.map((agent) => byAgent.get(agent) ?? { agent, runs: 0, errors: 0 });
  const maxRuns = Math.max(1, ...activity.map((t) => t.runs));

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col gap-8 overflow-y-auto border-r border-sidebar-border bg-sidebar px-4 py-6">
        <div className="flex items-center gap-2.5 px-2">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-primary" />
          <span className="font-heading text-2xl italic tracking-tight">SocialOps</span>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={brandId ? `${item.href}?brand_id=${brandId}` : item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm",
                  active
                    ? "border-accent bg-accent font-medium text-accent-foreground"
                    : "border-transparent text-foreground hover:bg-muted",
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex flex-col gap-3 border-t border-sidebar-border pt-6">
          <div className="px-2 text-[11px] tracking-[0.08em] text-muted-foreground uppercase">
            Pipelines
          </div>
          <div className="flex flex-col gap-3 px-2">
            {PIPELINES.map((p) => (
              <div key={p.label} className="flex flex-col gap-1.5">
                <span className="text-[13px] text-muted-foreground">{p.label}</span>
                <div className="flex flex-wrap gap-1.5">
                  {p.nodes.map((node, i) => (
                    <span
                      key={node}
                      className={cn(
                        "rounded px-2 py-1 font-mono text-xs",
                        p.model.includes(i)
                          ? "border border-accent bg-accent text-accent-foreground"
                          : "border border-border",
                      )}
                    >
                      {node}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-sidebar-border pt-6">
          <div className="px-2 text-[11px] tracking-[0.08em] text-muted-foreground uppercase">
            Agent activity
          </div>
          <div className="flex flex-col gap-3 px-2">
            {activity.map((t) => (
              <Link
                key={t.agent}
                href={brandId ? `/agents?brand_id=${brandId}` : "/agents"}
                className="flex flex-col gap-1.5"
              >
                <span className="flex justify-between gap-2 text-[13.5px]">
                  <span>{t.agent}</span>
                  <span className="text-muted-foreground tabular-nums">{t.runs}</span>
                </span>
                <span className="block h-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className={cn("block h-full", t.errors > 2 ? "bg-destructive/75" : "bg-primary/75")}
                    style={{ width: `${Math.round((t.runs / maxRuns) * 100)}%` }}
                  />
                </span>
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card px-3.5 py-3 text-xs leading-relaxed text-muted-foreground">
          <span className="text-foreground">Phase 1 &middot; local.</span> Ollama &middot; Postgres 16
          &middot; Redis 7. No live platform APIs; every reply is human-approved.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[58px] shrink-0 items-center justify-between gap-4 border-b border-border px-6.5">
          {error ? (
            <p className="text-sm text-destructive">Cannot reach the API. {error}</p>
          ) : brands === null ? (
            <div className="h-8 w-48 animate-pulse rounded-md bg-muted" />
          ) : (
            <BrandSwitcher
              brands={brands}
              current={currentBrand}
              open={brandOpen}
              setOpen={setBrandOpen}
              onPick={(id) => {
                router.push(`${pathname}?brand_id=${id}`);
                setBrandOpen(false);
              }}
            />
          )}
          <QueueMeter />
        </header>

        <main className="min-w-0 flex-1 px-6.5 py-6.5">{children}</main>
      </div>
    </div>
  );
}

function BrandSwitcher({
  brands,
  current,
  open,
  setOpen,
  onPick,
}: {
  brands: Brand[];
  current: Brand | null;
  open: boolean;
  setOpen: (v: boolean) => void;
  onPick: (id: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open, setOpen]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-[13px] hover:bg-muted"
      >
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: BRAND_HUES[brands.findIndex((b) => b.id === current?.id) % BRAND_HUES.length] }}
        />
        <span>{current?.name ?? "Select a brand"}</span>
        <span className="text-[10px] text-muted-foreground">&#9662;</span>
      </button>
      {open && (
        <div className="absolute top-10 right-0 z-20 flex w-56 flex-col rounded-lg border border-border bg-card p-1">
          {brands.map((brand, i) => (
            <button
              key={brand.id}
              type="button"
              onClick={() => onPick(brand.id)}
              className={cn(
                "flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-[13px] hover:bg-muted",
                brand.id === current?.id && "bg-muted",
              )}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: BRAND_HUES[i % BRAND_HUES.length] }}
              />
              <span>{brand.name}</span>
            </button>
          ))}
          <div className="px-2.5 pt-1.5 pb-1 text-[11.5px] leading-snug text-muted-foreground">
            brand_id lives in the URL, so a shared link resolves to the same view.
          </div>
        </div>
      )}
    </div>
  );
}

/** Polled every 2s. D18 cut the sampling table, so this reads live state. */
function QueueMeter() {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      if (document.hidden) return;
      try {
        const next = await api.queueStats();
        if (cancelled) return;
        setStats(next);
        setStale(false);
      } catch {
        if (!cancelled) setStale(true);
      }
    };

    const poll = () => void tick();

    poll();
    const timer = setInterval(poll, 2000);
    document.addEventListener("visibilitychange", poll);
    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", poll);
    };
  }, []);

  if (stats === null) {
    return <div className="h-5 w-40 animate-pulse rounded bg-muted" />;
  }

  return (
    <dl className={cn("flex items-center gap-2.5 text-[12.5px] tabular-nums", stale && "opacity-50")}>
      <Stat label="queued" value={stats.queued} loud={stats.queued > 0} />
      <Divider />
      <Stat label="running" value={stats.running} loud={stats.running > 0} />
      <Divider />
      <Stat label="failed" value={stats.failed} loud={stats.failed > 0} destructive />
    </dl>
  );
}

function Divider() {
  return <span className="h-3 w-px bg-border" />;
}

function Stat({
  label,
  value,
  loud,
  destructive,
}: {
  label: string;
  value: number;
  loud?: boolean;
  destructive?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-muted-foreground">{label}</span>
      <strong
        className={cn(
          "font-semibold",
          destructive && value > 0 ? "text-destructive" : loud ? "text-foreground" : "text-muted-foreground opacity-50",
        )}
      >
        {value}
      </strong>
    </div>
  );
}

function iconProps() {
  return { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
}

function NavInbox({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18 18" {...iconProps()}>
      <rect x="2.5" y="3.5" width="13" height="11" rx="2" />
      <path d="M2.5 10h3l1.5 2h4l1.5-2h3" />
    </svg>
  );
}
function NavContent({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18 18" {...iconProps()}>
      <rect x="2.5" y="3.5" width="13" height="11" rx="2" />
      <circle cx="6.5" cy="7.5" r="1.4" />
      <path d="M3 13l4-4 3 3 2-2 3 3" />
    </svg>
  );
}
function NavIdeas({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18 18" {...iconProps()}>
      <circle cx="9" cy="7.5" r="4" />
      <path d="M7.5 13h3M8 15h2" />
    </svg>
  );
}
function NavInsights({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18 18" {...iconProps()}>
      <path d="M3 14V8M7 14V4M11 14v-7M15 14v-3" />
    </svg>
  );
}
function NavAgents({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 18 18" {...iconProps()}>
      <rect x="3" y="6" width="12" height="8" rx="2" />
      <path d="M9 3v3" />
      <circle cx="6.5" cy="10" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="11.5" cy="10" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}
