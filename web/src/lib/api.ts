/**
 * Typed client for the SocialOps API.
 *
 * The base URL comes from the environment, never a literal — the browser
 * resolves it, so it cannot be the compose service name (hard rule #1).
 */
const BASE = process.env.NEXT_PUBLIC_API_URL;

export type Category = "question" | "complaint" | "praise" | "spam" | "other";
export type Urgency = "low" | "med" | "high";
export type CommentStatus = "new" | "triaged" | "drafted" | "replied" | "failed";
export type DraftStatus = "pending" | "approved" | "rejected" | "published";

export interface Brand {
  id: number;
  name: string;
}

export interface ReplyDraft {
  id: number;
  text: string;
  status: DraftStatus;
  final_text: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

export interface Comment {
  id: number;
  post_id: number;
  external_id: string;
  author: string;
  text: string;
  created_at: string;
  category: Category | null;
  sentiment: number | null;
  needs_reply: boolean | null;
  urgency: Urgency | null;
  status: CommentStatus;
  draft: ReplyDraft | null;
}

export interface QueueStats {
  queued: number;
  running: number;
  failed: number;
}

export type Platform = "x" | "instagram" | "linkedin";
export type ContentDraftStatus = "pending" | "approved" | "rejected";

/** The media agent's brand check against brand_rules_json (D16). */
export interface BrandCheck {
  passes: boolean;
  issues: string[];
}

export interface AssetAnalysis {
  description: string;
  detected_text: string[];
  brand_check: BrandCheck;
}

export interface ContentDraft {
  id: number;
  asset_id: number;
  platform: Platform;
  text: string;
  /** Stored apart from `text` so max_hashtags is checkable without parsing prose. */
  hashtags_json: string[];
  agent_run_id: number | null;
  status: ContentDraftStatus;
  final_text: string | null;
}

export interface Asset {
  id: number;
  brand_id: number;
  filename: string;
  storage_key: string;
  mime: string;
  /** null until the media agent has run — that is the "analysing" card. */
  analysis_json: AssetAnalysis | null;
  /** Whatever StorageBackend.url() returned. Relative today, presigned in Phase 4. */
  url: string;
  drafts: ContentDraft[];
}

export type AgentName = "triage" | "response" | "content" | "media";
export type AgentRunStatus = "ok" | "error";

export interface AgentRun {
  id: number;
  agent: AgentName;
  entity_type: string;
  entity_id: number;
  brand_id: number;
  status: AgentRunStatus;
  input_tokens: number;
  output_tokens: number;
  /** D15's three states. A JSON string when priced, null when it cannot be. */
  cost_usd: string | null;
  latency_ms: number;
  error: string | null;
  created_at: string;
}

export interface AgentTotals {
  agent: AgentName;
  runs: number;
  errors: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string | null;
  /** Runs with no price. Without it, SUM() silently under-reports spend. */
  unpriced: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
}

export interface AgentRunPage {
  runs: AgentRun[];
  totals: AgentTotals[];
  total_runs: number;
}

export interface AgentRunFilters {
  agent?: AgentName;
  status?: AgentRunStatus;
  entity_type?: string;
  entity_id?: number;
}

/**
 * Resolve a path the API handed us against the API's origin.
 *
 * `asset.url` is deliberately relative under local disk — it names an API route,
 * because a directory has no address a browser can reach. In Phase 4 it is an
 * absolute presigned S3 URL, so this must not clobber one that is already
 * absolute.
 */
export function apiUrl(path: string): string {
  return /^https?:\/\//.test(path) ? path : `${BASE ?? ""}${path}`;
}

/** Throws with the API's own message so callers can render it inline. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Next inlines NEXT_PUBLIC_* at build time, so an unset variable becomes the
  // literal string "undefined" and `${BASE}${path}` turns into a RELATIVE url:
  // the browser resolves "undefined/brands" against the Next dev server and
  // gets its 404 page. The symptom is then an inline error reading
  // "404: <!DOCTYPE html>...", which sends you looking at the API. Named here
  // instead, at the one place every call passes through.
  if (!BASE) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. It is the browser's address for the API " +
        "(the browser cannot resolve the compose service name), and compose reads " +
        "it from .env.",
    );
  }

  // A hand-set Content-Type on a FormData body strips the multipart boundary
  // the browser generates, and the server then parses zero parts. Let the
  // browser set it.
  const isMultipart = init?.body instanceof FormData;

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...(isMultipart ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (cause) {
    // fetch rejects with a bare "Failed to fetch" for DNS, connection refused,
    // CORS and an offline tab alike. Rendering that verbatim in the top bar
    // tells a marketing manager nothing; the address does.
    throw new Error(`Cannot reach the API at ${BASE}.`, { cause });
  }

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body ? `${response.status}: ${body.slice(0, 200)}` : `${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  brands: () => request<Brand[]>("/brands"),

  comments: (brandId: number, filters: { category?: string; status?: string } = {}) => {
    const params = new URLSearchParams({ brand_id: String(brandId), limit: "100" });
    if (filters.category) params.set("category", filters.category);
    if (filters.status) params.set("status", filters.status);
    return request<Comment[]>(`/comments?${params}`);
  },

  queueStats: () => request<QueueStats>("/queue/stats"),

  updateDraft: (id: number, body: { status?: DraftStatus; final_text?: string; approved_by?: string }) =>
    request<ReplyDraft>(`/reply_drafts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  bulkUpdate: (ids: number[], status: DraftStatus, approvedBy = "demo-user") =>
    request<ReplyDraft[]>("/reply_drafts/bulk", {
      method: "PATCH",
      body: JSON.stringify({ ids, status, approved_by: approvedBy }),
    }),

  assets: (brandId: number) =>
    request<Asset[]>(`/assets?brand_id=${brandId}`),

  uploadAsset: (brandId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ asset: Asset; enqueued: boolean }>(`/assets?brand_id=${brandId}`, {
      method: "POST",
      body: form,
    });
  },

  updateContentDraft: (id: number, body: { status?: ContentDraftStatus; final_text?: string }) =>
    request<ContentDraft>(`/content_drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  agentRuns: (brandId: number, filters: AgentRunFilters = {}) => {
    const params = new URLSearchParams({ brand_id: String(brandId), limit: "100" });
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined) params.set(key, String(value));
    }
    return request<AgentRunPage>(`/agent_runs?${params}`);
  },
};
