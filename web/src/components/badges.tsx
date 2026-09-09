import { Badge } from "@/components/ui/badge";
import type { Category, CommentStatus, DraftStatus, Urgency } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Colour lives only on badges (UI brief). Everything else in the table is
 * neutral, so a scan down the sentiment column reads as a signal rather than
 * competing with the surrounding chrome.
 */

/** D8's five buckets, in order. An ordinal deserves an ordinal ramp: red through
 *  grey to green, so severity is legible without reading the label. */
const SENTIMENT = [
  { label: "hostile", className: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200" },
  { label: "negative", className: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200" },
  { label: "neutral", className: "bg-muted text-muted-foreground" },
  { label: "positive", className: "bg-teal-100 text-teal-900 dark:bg-teal-950 dark:text-teal-200" },
  { label: "delighted", className: "bg-emerald-200 text-emerald-950 dark:bg-emerald-900 dark:text-emerald-100" },
];

export function SentimentBadge({ value }: { value: number | null }) {
  if (value === null) return <Dash />;
  const bucket = SENTIMENT[Math.min(4, Math.max(0, value + 2))];
  return (
    <Badge variant="secondary" className={cn("font-normal", bucket.className)}>
      {bucket.label}
    </Badge>
  );
}

const URGENCY: Record<Urgency, string> = {
  low: "bg-muted text-muted-foreground",
  med: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  high: "bg-rose-600 text-white dark:bg-rose-700",
};

export function UrgencyBadge({ value }: { value: Urgency | null }) {
  if (value === null) return <Dash />;
  // Only `high` is loud. If everything is urgent, nothing is.
  return (
    <Badge variant="secondary" className={cn("font-normal", URGENCY[value])}>
      {value}
    </Badge>
  );
}

export function CategoryBadge({ value }: { value: Category | null }) {
  if (value === null) return <Dash />;
  return (
    <Badge variant="outline" className="font-normal text-foreground">
      {value}
    </Badge>
  );
}

const DRAFT_STATUS: Record<DraftStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  approved: "bg-primary/10 text-primary",
  rejected: "bg-muted text-muted-foreground line-through",
  published: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
};

export function DraftStatusBadge({ value }: { value: DraftStatus }) {
  return (
    <Badge variant="secondary" className={cn("font-normal", DRAFT_STATUS[value])}>
      {value}
    </Badge>
  );
}

export function CommentStatusBadge({ value }: { value: CommentStatus }) {
  return (
    <Badge variant="outline" className="font-normal text-muted-foreground">
      {value}
    </Badge>
  );
}

/** An em dash, never a zero. A value that has not been produced yet is not the
 *  same as a value of nothing — the same distinction D15 makes about cost. */
function Dash() {
  return <span className="text-muted-foreground">—</span>;
}
