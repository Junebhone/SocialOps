"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, type Brand, type QueueStats } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/inbox", label: "Inbox" },
  { href: "/content", label: "Content" },
  { href: "/agents", label: "Agents" },
];

/**
 * Left sidebar, top bar with a brand selector and live queue stats.
 *
 * `brand_id` lives in the URL, never in a session (D17). The API is stateless,
 * so a link someone pastes into Slack has to resolve to the same view they were
 * looking at.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const params = useSearchParams();
  const brandId = params.get("brand_id");

  const [brands, setBrands] = useState<Brand[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .brands()
      .then((rows) => {
        setBrands(rows);
        // Land on a brand rather than an empty page; the URL then carries it.
        if (!brandId && rows.length > 0) {
          router.replace(`${pathname}?brand_id=${rows[0].id}`);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [brandId, pathname, router]);

  return (
    <div className="flex min-h-screen">
      <aside className="w-52 shrink-0 border-r border-border bg-sidebar">
        <div className="px-5 py-5 text-[15px] font-semibold tracking-tight">SocialOps</div>
        <nav className="px-2">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={brandId ? `${item.href}?brand_id=${brandId}` : item.href}
                className={cn(
                  "block rounded-md px-3 py-1.5 text-sm",
                  active
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border px-6">
          {error ? (
            <p className="text-sm text-rose-600">Cannot reach the API. {error}</p>
          ) : brands === null ? (
            <div className="h-8 w-48 animate-pulse rounded-md bg-muted" />
          ) : (
            <Select
              value={brandId ?? undefined}
              onValueChange={(value) => router.push(`${pathname}?brand_id=${value}`)}
            >
              <SelectTrigger className="w-56" aria-label="Brand">
                <SelectValue placeholder="Select a brand" />
              </SelectTrigger>
              <SelectContent>
                {brands.map((brand) => (
                  <SelectItem key={brand.id} value={String(brand.id)}>
                    {brand.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <QueueMeter />
        </header>

        <main className="min-w-0 flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}

/** Polled every 2s. D18 cut the sampling table, so this reads live state. */
function QueueMeter() {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const tick = () =>
      api
        .queueStats()
        .then((next) => {
          if (!cancelled) {
            setStats(next);
            setStale(false);
          }
        })
        .catch(() => !cancelled && setStale(true));

    tick();
    const timer = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (stats === null) {
    return <div className="h-5 w-40 animate-pulse rounded bg-muted" />;
  }

  return (
    <dl className={cn("flex items-center gap-5 text-sm", stale && "opacity-50")}>
      <Stat label="queued" value={stats.queued} />
      <Stat label="running" value={stats.running} />
      <Stat
        label="failed"
        value={stats.failed}
        className={stats.failed > 0 ? "text-rose-600" : undefined}
      />
    </dl>
  );
}

function Stat({ label, value, className }: { label: string; value: number; className?: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("font-mono tabular-nums", className)}>{value}</dd>
    </div>
  );
}
