"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { CategoryBadge, DraftStatusBadge, SentimentBadge, UrgencyBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { api, type Comment, type DraftStatus } from "@/lib/api";

type Filter = "all" | "needs_review" | "published";

const FILTERS: { key: Filter; label: string; status?: string }[] = [
  { key: "needs_review", label: "Needs review", status: "drafted" },
  { key: "published", label: "Published", status: "replied" },
  { key: "all", label: "All" },
];

export function Inbox() {
  const brandId = Number(useSearchParams().get("brand_id"));

  const [comments, setComments] = useState<Comment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("needs_review");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  // Bumped on every load; a response that is not the newest is dropped.
  //
  // Three things call `load` — the brand/filter effect, a 5s poll, and every
  // approve/reject — so several requests are routinely in flight at once, and
  // fetch gives no ordering guarantee. Switching brand while a slow request is
  // outstanding let the older response land last and paint ANOTHER BRAND'S
  // comments into the table, which is precisely the failure D17 made brand_id
  // required to prevent.
  const generation = useRef(0);

  const load = useCallback(async () => {
    if (!brandId) return;
    const mine = ++generation.current;
    try {
      const status = FILTERS.find((f) => f.key === filter)?.status;
      const rows = await api.comments(brandId, status ? { status } : {});
      if (mine !== generation.current) return;
      setComments(rows);
      setError(null);
    } catch (err) {
      if (mine !== generation.current) return;
      setError((err as Error).message);
    }
  }, [brandId, filter]);

  useEffect(() => {
    setComments(null);
    setSelected(new Set());
    void load();
  }, [load]);

  // The worker is still draining while someone reads this page, so refresh
  // rather than leaving a stale table that quietly stops matching the queue.
  //
  // Suspended while a draft is open in the textarea: the refresh re-renders the
  // row under the cursor, and a status that changed server-side swaps the edit
  // controls out from under a half-typed reply. Suspended in a hidden tab for
  // the same reason as the queue meter — step 9 measures this API under load.
  useEffect(() => {
    if (editing !== null) return;
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 5000);
    return () => clearInterval(timer);
  }, [load, editing]);

  const pending = (comments ?? []).filter((c) => c.draft?.status === "pending");
  const selectable = pending.map((c) => c.draft!.id);

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
      setSelected(new Set());
      setEditing(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const setStatus = (id: number, status: DraftStatus) =>
    act(() => api.updateDraft(id, { status, approved_by: "demo-user" }));

  const saveEdit = (id: number) =>
    act(() => api.updateDraft(id, { status: "approved", final_text: editText, approved_by: "demo-user" }));

  if (!brandId) {
    return <Empty title="No brand selected" body="Pick a brand in the top bar to see its inbox." />;
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

        <div className="flex items-center gap-3">
          {selected.size > 0 && (
            <span className="text-sm text-muted-foreground">{selected.size} selected</span>
          )}
          <Button
            size="sm"
            disabled={selected.size === 0 || busy}
            onClick={() => act(() => api.bulkUpdate([...selected], "approved"))}
          >
            Approve selected
          </Button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200">
          {error}
        </p>
      )}

      {comments === null ? (
        <LoadingRows />
      ) : comments.length === 0 ? (
        <Empty
          title="Nothing here yet"
          body={
            filter === "needs_review"
              ? "No drafts are waiting. Run make replay to bring comments in."
              : "No comments match this filter."
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-9">
                <Checkbox
                  aria-label="Select all"
                  checked={selectable.length > 0 && selected.size === selectable.length}
                  onCheckedChange={(value) =>
                    setSelected(value ? new Set(selectable) : new Set())
                  }
                  disabled={selectable.length === 0}
                />
              </TableHead>
              <TableHead className="w-28">Category</TableHead>
              <TableHead className="w-28">Sentiment</TableHead>
              <TableHead className="w-20">Urgency</TableHead>
              <TableHead>Comment</TableHead>
              <TableHead>Draft reply</TableHead>
              <TableHead className="w-44 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {comments.map((comment) => {
              const draft = comment.draft;
              const isPending = draft?.status === "pending";
              return (
                <TableRow key={comment.id} className="group align-top">
                  <TableCell className="py-3">
                    {isPending && (
                      <Checkbox
                        aria-label={`Select comment ${comment.id}`}
                        checked={selected.has(draft.id)}
                        onCheckedChange={(value) =>
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (value) next.add(draft.id);
                            else next.delete(draft.id);
                            return next;
                          })
                        }
                      />
                    )}
                  </TableCell>
                  <TableCell className="py-3">
                    <CategoryBadge value={comment.category} />
                  </TableCell>
                  <TableCell className="py-3">
                    <SentimentBadge value={comment.sentiment} />
                  </TableCell>
                  <TableCell className="py-3">
                    <UrgencyBadge value={comment.urgency} />
                  </TableCell>
                  <TableCell className="max-w-xs py-3">
                    <p className="truncate">{comment.text}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{comment.author}</p>
                  </TableCell>
                  <TableCell className="max-w-md py-3">
                    {editing === draft?.id ? (
                      <Textarea
                        value={editText}
                        onChange={(event) => setEditText(event.target.value)}
                        rows={3}
                        autoFocus
                      />
                    ) : draft ? (
                      <>
                        <p className="whitespace-pre-wrap">{draft.final_text ?? draft.text}</p>
                        <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                          <DraftStatusBadge value={draft.status} />
                          {draft.final_text && <span>edited</span>}
                          {draft.approved_by && <span>by {draft.approved_by}</span>}
                        </p>
                      </>
                    ) : (
                      <span className="text-muted-foreground">
                        {comment.needs_reply === false ? "No reply needed" : "Waiting for the agent"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="py-3 text-right">
                    {draft && editing === draft.id ? (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" disabled={busy} onClick={() => saveEdit(draft.id)}>
                          Save and approve
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                          Cancel
                        </Button>
                      </div>
                    ) : isPending ? (
                      <div className="flex justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                        <Button size="sm" disabled={busy} onClick={() => setStatus(draft.id, "approved")}>
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditing(draft.id);
                            setEditText(draft.final_text ?? draft.text);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busy}
                          onClick={() => setStatus(draft.id, "rejected")}
                        >
                          Reject
                        </Button>
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading comments">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="h-12 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
