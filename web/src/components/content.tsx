"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";

import { BrandCheckBadge, ContentDraftStatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  apiUrl,
  type Asset,
  type ContentDraft,
  type ContentDraftStatus,
  type Platform,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/** Fixed order, so the three columns mean the same thing on every card. */
const PLATFORMS: Platform[] = ["x", "instagram", "linkedin"];

const ACCEPT = { "image/png": [], "image/jpeg": [], "image/webp": [] };

/** Matches MAX_UPLOAD_BYTES in the API, so an oversized file is refused here
 *  rather than after a ten-megabyte round trip. */
const MAX_BYTES = 10 * 1024 * 1024;

export function Content() {
  const brandId = Number(useSearchParams().get("brand_id"));

  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  // Same guard as the Inbox: several loads are routinely in flight — the brand
  // effect, the analysis poll, and every approve — and an older response
  // landing last would paint another brand's assets.
  const generation = useRef(0);

  const load = useCallback(async () => {
    if (!brandId) return;
    const mine = ++generation.current;
    try {
      const rows = await api.assets(brandId);
      if (mine !== generation.current) return;
      setAssets(rows);
      setError(null);
    } catch (err) {
      if (mine !== generation.current) return;
      setError((err as Error).message);
    }
  }, [brandId]);

  useEffect(() => {
    setAssets(null);
    void load();
  }, [load]);

  // Poll only while something is still being analysed, and stop when it is not.
  // A media call plus a content call is 15-35s on a warm 9B model, so the card
  // has to fill itself in — but a page of finished assets does not change on
  // its own, and polling it forever is load inside step 9's measurements.
  const analysing = (assets ?? []).some((asset) => asset.analysis_json === null);
  useEffect(() => {
    if (!analysing) return;
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 3000);
    return () => clearInterval(timer);
  }, [analysing, load]);

  const onDrop = useCallback(
    async (files: File[]) => {
      if (!brandId || files.length === 0) return;
      setUploading(true);
      setError(null);
      try {
        // Sequential, not Promise.all. Each upload starts a vision call on a
        // single local model that serialises anyway, and firing five at once
        // only makes the last one time out.
        for (const file of files) {
          await api.uploadAsset(brandId, file);
        }
        await load();
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setUploading(false);
      }
    },
    [brandId, load],
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxSize: MAX_BYTES,
    disabled: !brandId || uploading,
  });

  if (!brandId) {
    return (
      <Empty
        title="No brand selected"
        body="Pick a brand in the top bar to see its photos."
      />
    );
  }

  const rejection = fileRejections[0]?.errors[0]?.message;

  return (
    <div className="space-y-5">
      <div
        {...getRootProps()}
        className={cn(
          "flex items-center justify-center rounded-lg border border-dashed px-4 py-7 text-sm transition-colors",
          uploading
            ? "cursor-wait border-border text-muted-foreground"
            : "cursor-pointer",
          isDragActive
            ? "border-primary bg-primary/5 text-primary"
            : "border-border text-muted-foreground hover:border-foreground/30",
        )}
      >
        <input {...getInputProps()} />
        {uploading
          ? "Uploading…"
          : isDragActive
            ? "Drop to upload"
            : "Drop a product photo here, or click to choose one"}
      </div>

      {(error || rejection) && (
        <p className="rounded-md border border-status-bad-bg bg-status-bad-bg px-3 py-2 text-sm text-status-bad">
          {error ?? rejection}
        </p>
      )}

      {assets === null ? (
        <LoadingCards />
      ) : assets.length === 0 ? (
        <Empty
          title="No photos yet"
          body="Upload a product photo. The agents describe it, check it against your brand rules, and draft a caption for each platform."
        />
      ) : (
        assets.map((asset) => <AssetCard key={asset.id} asset={asset} onChange={load} />)
      )}
    </div>
  );
}

function AssetCard({ asset, onChange }: { asset: Asset; onChange: () => Promise<void> }) {
  const analysis = asset.analysis_json;
  const byPlatform = new Map(asset.drafts.map((draft) => [draft.platform, draft]));

  return (
    <article className="overflow-hidden rounded-lg border border-border">
      <div className="flex gap-4 p-4">
        {/* next/image is not used deliberately: the src comes from an
            env-configured API origin, so `images.remotePatterns` would mean a
            hostname in a config file (hard rule #1), and these are already
            downscaled demo assets with nothing left to optimise. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={apiUrl(asset.url)}
          alt={analysis?.description ?? asset.filename}
          className="h-24 w-24 shrink-0 rounded-md border border-border bg-muted object-cover"
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="truncate font-medium">{asset.filename}</p>
            {analysis && <BrandCheckBadge value={analysis.brand_check} />}
          </div>

          {analysis === null ? (
            <p className="mt-1 text-muted-foreground">Analysing the photo…</p>
          ) : (
            <>
              <p className="mt-1 max-w-prose text-muted-foreground">{analysis.description}</p>

              {analysis.detected_text.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-1">
                  {analysis.detected_text.map((line, index) => (
                    <li
                      key={`${line}-${index}`}
                      className="rounded border border-border px-1.5 py-0.5 text-xs"
                    >
                      {line}
                    </li>
                  ))}
                </ul>
              )}

              {!analysis.brand_check.passes && (
                <ul className="mt-2 max-w-prose list-disc space-y-0.5 pl-4">
                  {analysis.brand_check.issues.map((issue, index) => (
                    <li key={`${issue}-${index}`}>{issue}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 divide-y divide-border border-t border-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {PLATFORMS.map((platform) => {
          const draft = byPlatform.get(platform);
          return draft ? (
            <DraftColumn key={platform} draft={draft} onChange={onChange} />
          ) : (
            <div key={platform} className="p-4">
              <p className="text-muted-foreground">{platform}</p>
              <div className="mt-2 h-4 w-4/5 animate-pulse rounded bg-muted" />
              <div className="mt-1.5 h-4 w-3/5 animate-pulse rounded bg-muted" />
            </div>
          );
        })}
      </div>
    </article>
  );
}

function DraftColumn({
  draft,
  onChange,
}: {
  draft: ContentDraft;
  onChange: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft.final_text ?? draft.text);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(body: { status?: ContentDraftStatus; final_text?: string }) {
    setBusy(true);
    setError(null);
    try {
      await api.updateContentDraft(draft.id, body);
      setEditing(false);
      await onChange();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="group flex min-w-0 flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">{draft.platform}</span>
        <ContentDraftStatusBadge value={draft.status} />
      </div>

      {editing ? (
        <Textarea value={text} onChange={(event) => setText(event.target.value)} rows={4} autoFocus />
      ) : (
        <p className="whitespace-pre-wrap">{draft.final_text ?? draft.text}</p>
      )}

      {draft.hashtags_json.length > 0 && !editing && (
        <p className="text-xs text-muted-foreground">
          {draft.hashtags_json.map((tag) => `#${tag}`).join(" ")}
        </p>
      )}

      {draft.final_text && !editing && <p className="text-xs text-muted-foreground">edited</p>}

      {error && <p className="text-xs text-status-bad">{error}</p>}

      <div className="mt-auto flex flex-wrap gap-1 pt-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        {editing ? (
          <>
            <Button size="sm" disabled={busy} onClick={() => act({ status: "approved", final_text: text })}>
              Save and approve
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" disabled={busy} onClick={() => act({ status: "approved" })}>
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setText(draft.final_text ?? draft.text);
                setEditing(true);
              }}
            >
              Edit
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => act({ status: "rejected" })}>
              Reject
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function LoadingCards() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading photos">
      {Array.from({ length: 2 }).map((_, index) => (
        <div key={index} className="h-48 animate-pulse rounded-lg bg-muted" />
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
