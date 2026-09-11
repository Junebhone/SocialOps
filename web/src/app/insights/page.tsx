import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { Insights } from "@/components/insights";

export const metadata = { title: "Insights · SocialOps" };

export default function InsightsPage() {
  // useSearchParams needs a Suspense boundary in the App Router; brand_id lives
  // in the URL (D17), so every page that reads it needs one.
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AppShell>
        <div className="mb-5">
          <h1 className="text-lg font-semibold tracking-tight">Insights</h1>
          <p className="text-sm text-muted-foreground">
            What your real posts actually did, and the patterns behind it.
          </p>
        </div>
        <Insights />
      </AppShell>
    </Suspense>
  );
}
