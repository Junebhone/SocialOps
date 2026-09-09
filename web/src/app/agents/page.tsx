import { Suspense } from "react";

import { Agents } from "@/components/agents";
import { AppShell } from "@/components/app-shell";

export const metadata = { title: "Agents · SocialOps" };

export default function AgentsPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AppShell>
        <div className="mb-5">
          <h1 className="text-lg font-semibold tracking-tight">Agents</h1>
          <p className="text-sm text-muted-foreground">
            Every model call this brand has made, what it cost, and how long it took.
          </p>
        </div>
        <Agents />
      </AppShell>
    </Suspense>
  );
}
