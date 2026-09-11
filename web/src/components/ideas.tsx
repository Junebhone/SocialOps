"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ContentIdeaStatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { api, type ContentIdea } from "@/lib/api";
import { cn } from "@/lib/utils";

type Filter = "proposed" | "approved" | "all";

const FILTERS: { key: Filter; label: string; status?: "proposed" | "approved" }[] = [
  { key: "proposed", label: "New", status: "proposed" },
  { key: "approved", label: "Approved", status: "approved" },
  { key: "all", label: "All" },
];

// How long to keep polling after a click before giving up and telling the
// reviewer to check the Agents page — matches the Content page's own
// "poll while something is still being produced" pattern, but ideation has
// no per-row marker to poll against (there is no row until the job writes
// one), so this counts attempts instead of reading a null field.
const GENERATE_POLL_MS = 2000;
const GENERATE_MAX_POLLS = 30; // ~60s, generous for a cold local model

export function Ideas() {
  const brandId = Number(useSearchParams().get("brand_id"));

  const [ideas, setIdeas] = useState<ContentIdea[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("proposed");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<number>>(new Set());

  // Same guard as Inbox/Content: several loads can be in flight (the brand
  // effect, the generate poll, every approve), and an older response landing
  // last would paint another brand's ideas.
  const generation = useRef(0);

  const load = useCallback(async () => {
    if (!brandId) return null;
    const mine = ++generation.current;
    try {
      const status = FILTERS.find((f) => f.key === filter)?.status;
      const rows = await api.contentIdeas(brandId, status ? { status } : {});
      if (mine !== generation.current) return null;
      setIdeas(rows);
      setError(null);
      return rows;
    } catch (err) {
      if (mine !== generation.current) return null;
      setError((err as Error).message);
      return null;
    }
  }, [brandId, filter]);

  useEffect(() => {
    setIdeas(null);
    void load();
  }, [load]);

  async function generate() {
    if (!brandId || generating) return;
    setGenerating(true);
    setError(null);
    const before = new Set((ideas ?? []).map((i) => i.id));

    try {
      await api.generateIdeas(brandId);

      for (let attempt = 0; attempt < GENERATE_MAX_POLLS; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, GENERATE_POLL_MS));
        const rows = await load();
        const fresh = (rows ?? []).filter((i) => !before.has(i.id));
        if (fresh.length > 0) {
          // Marks them for the entrance animation below, then lets it play
          // once — React keys make this fire only for genuinely new cards.
          setSeenIds((prev) => new Set([...prev, ...fresh.map((i) => i.id)]));
          break;
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  }

  async function setStatus(id: number, status: "approved" | "rejected") {
    setBusyId(id);
    setError(null);
    try {
      await api.updateContentIdea(id, status);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  if (!brandId) {
    return <Empty title="No brand selected" body="Pick a brand in the top bar to see its ideas." />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <Button
              key={f.key}
              size="sm"
              variant={filter === f.key ? "secondary" : "ghost"}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </Button>
          ))}
        </div>

        <Button size="sm" onClick={generate} disabled={generating} className="relative overflow-hidden">
          {generating && (
            <span className="absolute inset-0 -translate-x-full animate-[shimmer_1.4s_infinite] bg-gradient-to-r from-transparent via-white/25 to-transparent" />
          )}
          {generating ? "Generating…" : "Generate ideas"}
        </Button>
      </div>

      {error && (
        <p className="rounded-md border border-status-bad-bg bg-status-bad-bg px-3 py-2 text-sm text-status-bad">
          {error}
        </p>
      )}

      {ideas === null ? (
        <LoadingCards />
      ) : ideas.length === 0 ? (
        <Empty
          title="No ideas yet"
          body='Click "Generate ideas" to have the ideation agent propose a few content angles from your seeded trend signals.'
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ideas.map((idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              isNew={seenIds.has(idea.id)}
              busy={busyId === idea.id}
              onApprove={() => setStatus(idea.id, "approved")}
              onReject={() => setStatus(idea.id, "rejected")}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function IdeaCard({
  idea,
  isNew,
  busy,
  onApprove,
  onReject,
}: {
  idea: ContentIdea;
  isNew: boolean;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <article
      className={cn(
        "group flex flex-col gap-2.5 rounded-lg border border-border p-4",
        "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm",
        isNew && "animate-in fade-in slide-in-from-bottom-2 duration-500",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <ContentIdeaStatusBadge value={idea.status} />
      </div>

      <p className="flex-1">{idea.text}</p>

      {idea.source_signal && (
        <p className="text-xs text-muted-foreground">Inspired by: {idea.source_signal}</p>
      )}

      {idea.status === "proposed" && (
        <div className="mt-1 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <Button size="sm" disabled={busy} onClick={onApprove}>
            Approve
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={onReject}>
            Reject
          </Button>
        </div>
      )}
    </article>
  );
}

function LoadingCards() {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
      aria-busy="true"
      aria-label="Loading ideas"
    >
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="h-32 animate-pulse rounded-lg bg-muted" />
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
