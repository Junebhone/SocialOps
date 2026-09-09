import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { Inbox } from "@/components/inbox";

export const metadata = { title: "Inbox · SocialOps" };

export default function InboxPage() {
  // useSearchParams needs a Suspense boundary in the App Router; brand_id lives
  // in the URL (D17), so every page that reads it needs one.
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AppShell>
        <div className="mb-5">
          <h1 className="text-lg font-semibold tracking-tight">Inbox</h1>
          <p className="text-sm text-muted-foreground">
            Agent-drafted replies, waiting on you. Approve one, or select several.
          </p>
        </div>
        <Inbox />
      </AppShell>
    </Suspense>
  );
}
