"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { DraftStatusBadge, SentimentBadge, UrgencyBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, type Comment, type DraftStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

type Filter = "all" | "needs_review" | "published";

const FILTERS: { key: Filter; label: string; status?: string }[] = [
  { key: "needs_review", label: "Needs review", status: "drafted" },
  { key: "published", label: "Published", status: "replied" },
  { key: "all", label: "All" },
];

const GRID_COLS = "grid-cols-[26px_118px_minmax(0,1fr)_minmax(0,1.1fr)_128px]";

interface Toast {
  message: string;
  undo: () => void;
}

/**
 * Color and weight are reserved for exceptions: category stays plain text,
 * and sentiment/urgency/status pills only render when they differ from the
 * common case (neutral sentiment, low/med urgency, a pending draft under the
 * Needs-review tab). A row of "question / neutral / low" repeated twenty
 * times is noise, not signal.
 */
export function Inbox() {
  const brandId = Number(useSearchParams().get("brand_id"));

  const [comments, setComments] = useState<Comment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("needs_review");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [hovered, setHovered] = useState<number | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);

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

  useEffect(() => {
    if (editing !== null) return;
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 5000);
    return () => clearInterval(timer);
  }, [load, editing]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const pending = (comments ?? []).filter((c) => c.draft?.status === "pending");
  const selectable = pending.map((c) => c.draft!.id);
  const allSelected = selectable.length > 0 && selected.size === selectable.length;

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const setStatus = (id: number, status: DraftStatus) =>
    act(() => api.updateDraft(id, { status, approved_by: "demo-user" }));

  const saveEdit = (id: number) =>
    act(() => api.updateDraft(id, { status: "approved", final_text: editText, approved_by: "demo-user" })).then(
      () => setEditing(null),
    );

  // Reject is reversible for a few seconds — apply it, then offer a way back
  // rather than a confirmation dialog up front.
  function reject(id: number) {
    void act(() => api.updateDraft(id, { status: "rejected" }));
    setToast({
      message: "Rejected",
      undo: () => void act(() => api.updateDraft(id, { status: "pending" })),
    });
  }

  function bulkApprove() {
    const ids = [...selected];
    void act(() => api.bulkUpdate(ids, "approved")).then(() => setSelected(new Set()));
  }

  function bulkReject() {
    const ids = [...selected];
    void act(() => api.bulkUpdate(ids, "rejected")).then(() => setSelected(new Set()));
    setToast({
      message: `Rejected ${ids.length}`,
      undo: () => void act(() => api.bulkUpdate(ids, "pending")),
    });
  }

  if (!brandId) {
    return <Empty title="No brand selected" body="Pick a brand in the top bar to see its inbox." />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-1 border-b border-border">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-[13.5px]",
              filter === f.key
                ? "border-primary font-medium text-foreground"
                : "border-transparent text-muted-foreground",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-accent bg-accent px-3.5 py-2.5 text-[13px] text-accent-foreground">
          <span className="tabular-nums">{selected.size} selected</span>
          <span className="ml-auto flex gap-1.5">
            <Button size="sm" disabled={busy} onClick={bulkApprove}>
              Approve {selected.size}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              className="border border-accent-foreground/30 text-accent-foreground hover:bg-accent-foreground/10"
              onClick={bulkReject}
            >
              Reject
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-accent-foreground hover:bg-accent-foreground/10"
              onClick={() => setSelected(new Set())}
            >
              Clear
            </Button>
          </span>
        </div>
      )}

      {error && (
        <p className="rounded-md border border-status-bad-bg bg-status-bad-bg px-3 py-2 text-sm text-status-bad">
          {error}
        </p>
      )}

      {comments === null ? (
        <LoadingRows />
      ) : comments.length === 0 ? (
        <Empty
          title="Queue clear"
          body={
            filter === "needs_review"
              ? "Nothing in this view. New comments arrive on the poll."
              : "No comments match this filter."
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <div className="min-w-[920px]">
            <div
              className={cn(
                "grid items-center gap-3.5 border-b border-border px-4 py-2.25 text-[11px] tracking-[0.08em] text-muted-foreground uppercase",
                GRID_COLS,
              )}
            >
              <input
                type="checkbox"
                aria-label="Select all"
                checked={allSelected}
                disabled={selectable.length === 0}
                onChange={(e) => setSelected(e.target.checked ? new Set(selectable) : new Set())}
                className="m-0 h-3.5 w-3.5 cursor-pointer accent-primary"
              />
              <span>Signal</span>
              <span>Comment</span>
              <span>Draft reply</span>
              <span className="text-right">Action</span>
            </div>

            {comments.map((comment, i) => {
              const draft = comment.draft;
              const isPending = draft?.status === "pending";
              const isEditing = editing === draft?.id;
              const isHovered = hovered === comment.id;
              const showSentiment = comment.sentiment !== null && comment.sentiment !== 0;
              const showUrgency = comment.urgency === "high";
              const showStatus = draft && draft.status !== "pending";

              return (
                <div
                  key={comment.id}
                  onMouseEnter={() => setHovered(comment.id)}
                  onMouseLeave={() => setHovered((h) => (h === comment.id ? null : h))}
                  className={cn(
                    "grid items-start gap-3.5 px-4 py-2.75 transition-colors duration-[140ms]",
                    i < comments.length - 1 && "border-b border-row-border",
                    isHovered ? "bg-row-hover" : "bg-transparent",
                    GRID_COLS,
                  )}
                >
                  {isPending ? (
                    <input
                      type="checkbox"
                      aria-label={`Select comment ${comment.id}`}
                      checked={selected.has(draft.id)}
                      onChange={(e) =>
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(draft.id);
                          else next.delete(draft.id);
                          return next;
                        })
                      }
                      className="mt-0.5 h-3.5 w-3.5 cursor-pointer accent-primary"
                    />
                  ) : (
                    <span />
                  )}

                  <div className="flex flex-col items-start gap-1 pt-px">
                    <span className="text-[12.5px] text-muted-foreground">{comment.category ?? "—"}</span>
                    {showSentiment && <SentimentBadge value={comment.sentiment} />}
                    {showUrgency && <UrgencyBadge value={comment.urgency} />}
                  </div>

                  <div className="min-w-0">
                    <p className="text-pretty leading-[1.5]">{comment.text}</p>
                    <p className="mt-0.75 text-xs text-muted-foreground">{comment.author}</p>
                  </div>

                  <div className="min-w-0">
                    {isEditing ? (
                      <Textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        autoFocus
                        className="min-h-19 border-ring bg-background text-[13px] leading-[1.5]"
                      />
                    ) : draft ? (
                      <p
                        className={cn(
                          "text-pretty leading-[1.5]",
                          draft.status === "rejected" ? "text-muted-foreground line-through" : "text-foreground",
                        )}
                      >
                        {draft.final_text ?? draft.text}
                      </p>
                    ) : (
                      <span className="text-muted-foreground">
                        {comment.needs_reply === false ? "No reply needed" : "Waiting for the agent"}
                      </span>
                    )}
                    {showStatus && draft && (
                      <div className="mt-1.75">
                        <DraftStatusBadge value={draft.status} />
                      </div>
                    )}
                  </div>

                  <div
                    className={cn(
                      // flex-nowrap is load-bearing here, not cosmetic: three
                      // "sm" buttons don't fit an 128px column, so flex-wrap
                      // silently stacked them onto a second line — and since
                      // this div occupies layout space even at opacity-0, that
                      // wrap was inflating EVERY row's height, independent of
                      // how much comment/draft text it held. That was the
                      // actual source of the uniform oversized rows.
                      "flex flex-nowrap items-start justify-end gap-1 whitespace-nowrap transition-opacity duration-[140ms]",
                      isHovered || isEditing ? "opacity-100" : "opacity-0",
                    )}
                  >
                    {draft && isEditing ? (
                      <>
                        <Button size="xs" disabled={busy} className="bg-accent text-accent-foreground hover:bg-accent/80" onClick={() => saveEdit(draft.id)}>
                          Save
                        </Button>
                        <Button size="xs" variant="ghost" onClick={() => setEditing(null)}>
                          Cancel
                        </Button>
                      </>
                    ) : draft && draft.status !== "published" ? (
                      <>
                        <Button
                          size="xs"
                          disabled={busy}
                          className="bg-accent text-accent-foreground hover:bg-accent/80"
                          onClick={() => setStatus(draft.id, draft.status === "approved" ? "published" : "approved")}
                        >
                          {draft.status === "approved" ? "Publish" : "Approve"}
                        </Button>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => {
                            setEditing(draft.id);
                            setEditText(draft.final_text ?? draft.text);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={busy}
                          className="text-destructive"
                          onClick={() => reject(draft.id)}
                        >
                          Reject
                        </Button>
                      </>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3 rounded-full bg-foreground px-4.5 py-2.25 text-background shadow-none">
          <span className="text-[13px]">{toast.message}</span>
          <button
            className="rounded-full border border-background/30 px-2.5 py-1 text-[12px] hover:bg-background/10"
            onClick={() => {
              toast.undo();
              setToast(null);
            }}
          >
            Undo
          </button>
        </div>
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
      <p className="font-heading text-[17px]">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
