"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { EngagementRanking, MetricMix, StatTiles } from "@/components/insight-charts";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type Insight, type Post } from "@/lib/api";
import { cn } from "@/lib/utils";

const GENERATE_POLL_MS = 2000;
const GENERATE_MAX_POLLS = 30; // ~60s, generous for a cold local model

export function Insights() {
  const brandId = Number(useSearchParams().get("brand_id"));

  const [posts, setPosts] = useState<Post[] | null>(null);
  const [markers, setMarkers] = useState<Insight[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<number>>(new Set());

  const generation = useRef(0);

  const load = useCallback(async () => {
    if (!brandId) return null;
    const mine = ++generation.current;
    try {
      const [postRows, markerRows] = await Promise.all([api.posts(brandId), api.insights(brandId)]);
      if (mine !== generation.current) return null;
      setPosts(postRows);
      setMarkers(markerRows);
      setError(null);
      return markerRows;
    } catch (err) {
      if (mine !== generation.current) return null;
      setError((err as Error).message);
      return null;
    }
  }, [brandId]);

  useEffect(() => {
    setPosts(null);
    setMarkers(null);
    void load();
  }, [load]);

  async function generate() {
    if (!brandId || generating) return;
    setGenerating(true);
    setError(null);
    const before = new Set((markers ?? []).map((m) => m.id));

    try {
      await api.generateInsights(brandId);

      for (let attempt = 0; attempt < GENERATE_MAX_POLLS; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, GENERATE_POLL_MS));
        const rows = await load();
        const fresh = (rows ?? []).filter((m) => !before.has(m.id));
        if (fresh.length > 0) {
          setSeenIds((prev) => new Set([...prev, ...fresh.map((m) => m.id)]));
          break;
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  }

  if (!brandId) {
    return <Empty title="No brand selected" body="Pick a brand in the top bar to see its insights." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          Real metrics only &middot; no fabricated scores.
        </p>
        <Button size="sm" onClick={generate} disabled={generating} className="relative overflow-hidden">
          {generating && (
            <span className="absolute inset-0 -translate-x-full animate-[shimmer_1.4s_infinite] bg-gradient-to-r from-transparent via-white/25 to-transparent" />
          )}
          {generating ? "Analyzing…" : "Generate insights"}
        </Button>
      </div>

      {error && (
        <p className="rounded-md border border-status-bad-bg bg-status-bad-bg px-3 py-2 text-sm text-status-bad">
          {error}
        </p>
      )}

      {posts === null ? (
        <div className="h-40 animate-pulse rounded-lg bg-muted" />
      ) : posts.length === 0 ? (
        <Empty title="No posts yet" body="Insights need real posts with metrics to analyze." />
      ) : (
        <>
          <StatTiles posts={posts} />
          <div className="grid gap-4 lg:grid-cols-2">
            <EngagementRanking posts={posts} />
            <MetricMix posts={posts} />
          </div>
          <section>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Post</TableHead>
                  <TableHead className="text-right">Likes</TableHead>
                  <TableHead className="text-right">Comments</TableHead>
                  <TableHead className="text-right">Shares</TableHead>
                  <TableHead className="text-right">Engagement</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {posts.map((post) => {
                  const likes = post.metrics_json.likes ?? 0;
                  const comments = post.metrics_json.comments ?? 0;
                  const shares = post.metrics_json.shares ?? 0;
                  const score = likes + comments * 3 + shares * 5;
                  return (
                    <TableRow key={post.id}>
                      <TableCell className="max-w-xs py-2.5">
                        <p className="truncate">{post.text}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{post.external_id}</p>
                      </TableCell>
                      <TableCell className="py-2.5 text-right text-muted-foreground tabular-nums">
                        {likes.toLocaleString()}
                      </TableCell>
                      <TableCell className="py-2.5 text-right text-muted-foreground tabular-nums">
                        {comments.toLocaleString()}
                      </TableCell>
                      <TableCell className="py-2.5 text-right text-muted-foreground tabular-nums">
                        {shares.toLocaleString()}
                      </TableCell>
                      <TableCell className="py-2.5 text-right font-semibold tabular-nums">
                        {score.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            <p className="border-t border-border px-1 py-2.5 text-xs text-muted-foreground">
              engagement = likes + 3&times;comments + 5&times;shares, computed from real metrics only.
            </p>
          </section>
        </>
      )}

      <div>
        <h2 className="mb-1 font-heading text-[17px]">Markers</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Plain-language, grounded in the numbers above. No fabricated scores.
        </p>
        {markers === null ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : markers.length === 0 ? (
          <Empty
            title="No markers yet"
            body='Click "Generate insights" to have the insight agent find real patterns in your post performance.'
          />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {markers.map((marker) => (
              <div
                key={marker.id}
                className={cn(
                  "rounded-lg border border-border bg-card px-4 py-3.5",
                  seenIds.has(marker.id) && "animate-in fade-in slide-in-from-bottom-2 duration-500",
                )}
              >
                <p className="text-pretty text-sm leading-relaxed">{marker.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
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
