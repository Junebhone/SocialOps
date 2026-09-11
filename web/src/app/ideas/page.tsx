import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { Ideas } from "@/components/ideas";

export const metadata = { title: "Ideas · SocialOps" };

export default function IdeasPage() {
  // useSearchParams needs a Suspense boundary in the App Router; brand_id lives
  // in the URL (D17), so every page that reads it needs one.
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AppShell>
        <div className="mb-5">
          <h1 className="text-lg font-semibold tracking-tight">Ideas</h1>
          <p className="text-sm text-muted-foreground">
            Content angles from your seeded trend signals. Inspiration, not a pipeline trigger.
          </p>
        </div>
        <Ideas />
      </AppShell>
    </Suspense>
  );
}
