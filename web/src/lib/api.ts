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

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
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
};
