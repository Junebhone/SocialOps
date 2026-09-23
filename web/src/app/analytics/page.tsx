import { Suspense } from "react";

import { Analytics } from "@/components/analytics";
import { AppShell } from "@/components/app-shell";

export const metadata = { title: "Analytics · SocialOps" };

export default function AnalyticsPage() {
  // useSearchParams needs a Suspense boundary in the App Router; brand_id and
  // the date range live in the URL (D17), so a shared link is the same view.
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AppShell>
        <div className="mb-5">
          <h1 className="text-lg font-semibold tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            How customers feel, what they are writing about, and how fast they hear back.
          </p>
        </div>
        <Analytics />
      </AppShell>
    </Suspense>
  );
}
