import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { Content } from "@/components/content";

export const metadata = { title: "Content · SocialOps" };

export default function ContentPage() {
  // useSearchParams needs a Suspense boundary in the App Router; brand_id lives
  // in the URL (D17), so every page that reads it needs one.
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AppShell>
        <div className="mb-5">
          <h1 className="text-lg font-semibold tracking-tight">Content</h1>
          <p className="text-sm text-muted-foreground">
            Upload a product photo. One caption per platform, waiting on you.
          </p>
        </div>
        <Content />
      </AppShell>
    </Suspense>
  );
}
