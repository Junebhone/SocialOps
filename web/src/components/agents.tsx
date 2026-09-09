"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  api,
  type AgentName,
  type AgentRun,
  type AgentRunPage,
  type AgentTotals,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const AGENTS: AgentName[] = ["triage", "response", "content", "media"];

/**
 * The audit trail (hard rule #5), as a table.
 *
 * D1 cut the analytics agent and the charts on purpose. What earns its place
 * here is that every number is traceable to one row and one model call — so the
 * page is built for reading numbers, not for looking at them: tabular figures,
 * right-aligned, one accent and no colour except on a failure.
 */
export function Agents() {
  const params = useSearchParams();
  const router = useRouter();
  const brandId = Number(params.get("brand_id"));
  const agent = (params.get("agent") as AgentName | null) ?? undefined;
  const entityType = params.get("entity_type") ?? undefined;
  const entityId = params.get("entity_id") ? Number(params.get("entity_id")) : undefined;

  const [page, setPage] = useState<AgentRunPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generation = useRef(0);

  const load = useCallback(async () => {
    if (!brandId) return;
    const mine = ++generation.current;
    try {
      const next = await api.agentRuns(brandId, {
        agent,
        entity_type: entityType,
        entity_id: entityId,
      });
      if (mine !== generation.current) return;
      setPage(next);
      setError(null);
    } catch (err) {
      if (mine !== generation.current) return;
      setError((err as Error).message);
    }
  }, [brandId, agent, entityType, entityId]);

  useEffect(() => {
    setPage(null);
    void load();
  }, [load]);

  // Runs land while the queue drains, so the table refreshes — but only while
  // someone is looking at it.
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 5000);
    return () => clearInterval(timer);
  }, [load]);

  /** Filters live in the URL alongside brand_id, so a link to a filtered view
   *  resolves to the same view for whoever you send it to (D17). */
  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (value === null) next.delete(key);
    else next.set(key, value);
    if (key === "agent") {
      next.delete("entity_type");
      next.delete("entity_id");
    }
    router.push(`/agents?${next}`);
  };

  if (!brandId) {
    return <Empty title="No brand selected" body="Pick a brand in the top bar to see its runs." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-1">
        <Button size="sm" variant={!agent ? "secondary" : "ghost"} onClick={() => setParam("agent", null)}>
          All agents
        </Button>
        {AGENTS.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={agent === name ? "secondary" : "ghost"}
            onClick={() => setParam("agent", name)}
          >
            {name}
          </Button>
        ))}

        {entityType && entityId !== undefined && (
          <Button
            size="sm"
            variant="outline"
            className="ml-2"
            onClick={() => {
              setParam("entity_type", null);
              setParam("entity_id", null);
            }}
          >
            {entityType} {entityId} — clear
          </Button>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200">
          {error}
        </p>
      )}

      {page === null ? (
        <LoadingRows />
      ) : page.totals.length === 0 ? (
        <Empty
          title="No runs yet"
          body="Run make replay, or upload a photo on the Content page. Every agent call writes one row here."
        />
      ) : (
        <>
          <Totals totals={page.totals} />
          <Runs
            runs={page.runs}
            total={page.total_runs}
            onEntity={(type, id) => {
              const next = new URLSearchParams(params.toString());
              next.set("entity_type", type);
              next.set("entity_id", String(id));
              router.push(`/agents?${next}`);
            }}
          />
        </>
      )}
    </div>
  );
}

function Totals({ totals }: { totals: AgentTotals[] }) {
  const sum = (pick: (row: AgentTotals) => number) => totals.reduce((n, row) => n + pick(row), 0);

  return (
    <section>
      <h2 className="mb-2 font-medium">By agent</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Agent</TableHead>
            <TableHead className="text-right">Runs</TableHead>
            <TableHead className="text-right">Errors</TableHead>
            <TableHead className="text-right">Tokens in</TableHead>
            <TableHead className="text-right">Tokens out</TableHead>
            <TableHead className="text-right">Cost</TableHead>
            <TableHead className="text-right">p50</TableHead>
            <TableHead className="text-right">p95</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {totals.map((row) => (
            <TableRow key={row.agent}>
              <TableCell className="py-2.5 font-medium">{row.agent}</TableCell>
              <Num value={row.runs} />
              <TableCell
                className={cn("py-2.5 text-right font-mono tabular-nums", row.errors > 0 && "text-rose-600")}
              >
                {row.errors}
              </TableCell>
              <Num value={row.input_tokens} />
              <Num value={row.output_tokens} />
              <TableCell className="py-2.5 text-right font-mono tabular-nums">
                <Cost value={row.cost_usd} unpriced={row.unpriced} />
              </TableCell>
              <Num value={row.p50_latency_ms} suffix=" ms" />
              <Num value={row.p95_latency_ms} suffix=" ms" />
            </TableRow>
          ))}
          <TableRow className="border-t-2 border-border font-medium hover:bg-transparent">
            <TableCell className="py-2.5">All</TableCell>
            <Num value={sum((r) => r.runs)} />
            <TableCell
              className={cn(
                "py-2.5 text-right font-mono tabular-nums",
                sum((r) => r.errors) > 0 && "text-rose-600",
              )}
            >
              {sum((r) => r.errors)}
            </TableCell>
            <Num value={sum((r) => r.input_tokens)} />
            <Num value={sum((r) => r.output_tokens)} />
            <TableCell className="py-2.5 text-right font-mono tabular-nums">
              <Cost
                value={totals.every((r) => r.cost_usd === null)
                  ? null
                  : String(totals.reduce((n, r) => n + Number(r.cost_usd ?? 0), 0))}
                unpriced={sum((r) => r.unpriced)}
              />
            </TableCell>
            {/* No p50/p95 across agents: a percentile of a mixed population of
                fast-tier classifications and vision calls is not a number that
                describes anything. */}
            <TableCell className="py-2.5 text-right text-muted-foreground">—</TableCell>
            <TableCell className="py-2.5 text-right text-muted-foreground">—</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  );
}

function Runs({
  runs,
  total,
  onEntity,
}: {
  runs: AgentRun[];
  total: number;
  onEntity: (type: string, id: number) => void;
}) {
  return (
    <section>
      <h2 className="mb-2 font-medium">
        Runs{" "}
        <span className="font-normal text-muted-foreground">
          {runs.length < total ? `newest ${runs.length} of ${total}` : `${total}`}
        </span>
      </h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-40">Time</TableHead>
            <TableHead className="w-24">Agent</TableHead>
            <TableHead>Entity</TableHead>
            <TableHead className="text-right">Tokens</TableHead>
            <TableHead className="text-right">Cost</TableHead>
            <TableHead className="text-right">Latency</TableHead>
            <TableHead className="w-20 text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow key={run.id} className="align-top">
              <TableCell className="py-2.5 text-muted-foreground">
                <Timestamp value={run.created_at} />
              </TableCell>
              <TableCell className="py-2.5">{run.agent}</TableCell>
              <TableCell className="py-2.5">
                {/* D7's payoff: two indexed columns mean "what did this one
                    comment cost end to end" is a click, not a query. */}
                <button
                  type="button"
                  className="underline decoration-dotted underline-offset-2 hover:text-primary"
                  onClick={() => onEntity(run.entity_type, run.entity_id)}
                >
                  {run.entity_type} {run.entity_id}
                </button>
                {run.error && (
                  <p className="mt-0.5 max-w-md truncate text-xs text-rose-600" title={run.error}>
                    {run.error}
                  </p>
                )}
              </TableCell>
              <TableCell className="py-2.5 text-right font-mono tabular-nums">
                {run.input_tokens.toLocaleString()}
                <span className="text-muted-foreground"> / {run.output_tokens.toLocaleString()}</span>
              </TableCell>
              <TableCell className="py-2.5 text-right font-mono tabular-nums">
                <Cost value={run.cost_usd} unpriced={run.cost_usd === null ? 1 : 0} />
              </TableCell>
              <TableCell className="py-2.5 text-right font-mono tabular-nums">
                {run.latency_ms.toLocaleString()} ms
              </TableCell>
              <TableCell className="py-2.5 text-right">
                {run.status === "ok" ? (
                  <span className="text-muted-foreground">ok</span>
                ) : (
                  <Badge
                    variant="secondary"
                    className="font-normal bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200"
                  >
                    error
                  </Badge>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

function Num({ value, suffix = "" }: { value: number; suffix?: string }) {
  return (
    <TableCell className="py-2.5 text-right font-mono tabular-nums">
      {value.toLocaleString()}
      {suffix}
    </TableCell>
  );
}

/**
 * D15's three states, rendered as three different things.
 *
 * `null` is an em dash and never $0.00 — "we could not price this" is a
 * different fact from "this was free", and collapsing them produces a Phase 4
 * dashboard that reports Bedrock as free whenever a price lookup misses.
 */
function Cost({ value, unpriced }: { value: string | null; unpriced: number }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;

  const amount = Number(value);
  // Sub-cent calls are the normal case on a paid provider, so two decimals
  // would round a real cost to zero — the exact confusion D15 exists to stop.
  const formatted =
    amount === 0 ? "$0.00" : amount < 0.01 ? `$${amount.toFixed(6)}` : `$${amount.toFixed(2)}`;

  return (
    <>
      {formatted}
      {unpriced > 0 && (
        <span className="text-muted-foreground" title={`${unpriced} run(s) could not be priced`}>
          {" "}
          +{unpriced}?
        </span>
      )}
    </>
  );
}

/**
 * Rendered after mount, never on the server.
 *
 * `toLocaleTimeString` uses the runtime's locale and timezone, and the server's
 * are not the browser's — formatting this during SSR is a guaranteed hydration
 * mismatch, and the kind that is genuinely ours rather than an extension's.
 */
function Timestamp({ value }: { value: string }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    setText(new Date(value).toLocaleString(undefined, { dateStyle: "short", timeStyle: "medium" }));
  }, [value]);
  return <span className="font-mono tabular-nums">{text ?? " "}</span>;
}

function LoadingRows() {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading runs">
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-prose text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
