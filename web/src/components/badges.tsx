import { Badge } from "@/components/ui/badge";
import type {
  BrandCheck,
  Category,
  CommentStatus,
  ContentDraftStatus,
  ContentIdeaStatus,
  DraftStatus,
  Urgency,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Colour lives only on badges (UI brief). Everything else in the table is
 * neutral, so a scan down the sentiment column reads as a signal rather than
 * competing with the surrounding chrome.
 */

/** D8's five buckets, in order. An ordinal deserves an ordinal ramp: the same
 *  muted bad/neutral/good tokens badges use everywhere else, so severity is
 *  legible without reading the label — never the stock Tailwind brights. */
const SENTIMENT = [
  { label: "hostile", className: "bg-status-bad-bg text-status-bad" },
  { label: "negative", className: "bg-status-warn-bg text-status-warn" },
  { label: "neutral", className: "bg-muted text-muted-foreground" },
  { label: "positive", className: "bg-status-good-bg text-status-good" },
  { label: "delighted", className: "bg-status-good-bg text-status-good font-medium" },
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
  med: "bg-status-warn-bg text-status-warn",
  high: "bg-status-bad text-primary-foreground",
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
  approved: "bg-accent text-accent-foreground",
  rejected: "bg-muted text-muted-foreground line-through",
  published: "bg-status-good-bg text-status-good",
};

export function DraftStatusBadge({ value }: { value: DraftStatus }) {
  return (
    <Badge variant="secondary" className={cn("font-normal", DRAFT_STATUS[value])}>
      {value}
    </Badge>
  );
}

/** Content drafts never publish — the outbox drains reply drafts only — so this
 *  reuses the same ramp minus that state, rather than defining a second one. */
export function ContentDraftStatusBadge({ value }: { value: ContentDraftStatus }) {
  return (
    <Badge variant="secondary" className={cn("font-normal", DRAFT_STATUS[value])}>
      {value}
    </Badge>
  );
}

/**
 * The one place a failure is loud on this page.
 *
 * A passing check is a non-event and stays neutral; a failing one is the reason
 * someone opened the card. Colour lives only on the badge (UI brief) — the
 * issues themselves render as ordinary text, because they are content.
 */
export function BrandCheckBadge({ value }: { value: BrandCheck }) {
  return value.passes ? (
    <Badge variant="secondary" className="font-normal bg-status-good-bg text-status-good">
      brand check passed
    </Badge>
  ) : (
    <Badge variant="secondary" className="font-normal bg-status-bad-bg text-status-bad">
      {value.issues.length === 1 ? "1 brand issue" : `${value.issues.length} brand issues`}
    </Badge>
  );
}

const CONTENT_IDEA_STATUS: Record<ContentIdeaStatus, string> = {
  proposed: "bg-muted text-muted-foreground",
  approved: "bg-accent text-accent-foreground",
  rejected: "bg-muted text-muted-foreground line-through",
};

export function ContentIdeaStatusBadge({ value }: { value: ContentIdeaStatus }) {
  return (
    <Badge variant="secondary" className={cn("font-normal", CONTENT_IDEA_STATUS[value])}>
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
