const services = [
  { name: "web", detail: "This app, on port 3000" },
  { name: "api", detail: "FastAPI on port 8000, /health and /docs" },
  { name: "worker", detail: "arq consumer, no published port" },
  { name: "postgres", detail: "Postgres 16 on port 5432" },
  { name: "redis", detail: "Redis 7 on port 6379, backs the queue" },
];

const upcoming = [
  { name: "Inbox", detail: "Triaged comments and drafted replies, approved in batches" },
  { name: "Content", detail: "Upload an asset, get a draft per platform" },
  { name: "Agents", detail: "Every agent run, with tokens, cost, and latency" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-xl px-6 py-20">
      <h1 className="text-2xl font-semibold tracking-tight">SocialOps</h1>
      <p className="mt-2 max-w-prose text-muted-foreground">
        A command center where specialist agents triage comments and draft replies, and a
        person approves everything before it publishes.
      </p>

      <p className="mt-8 border-l-2 border-primary py-1 pl-3">
        The stack is running. Step 0 of 10 is complete: five containers, no features yet.
      </p>

      <section className="mt-10">
        <h2 className="font-medium">Running now</h2>
        <dl className="mt-3 divide-y divide-border border-y border-border">
          {services.map((service) => (
            <div key={service.name} className="flex gap-4 py-2.5">
              <dt className="w-24 shrink-0 font-mono text-xs leading-5 text-foreground">
                {service.name}
              </dt>
              <dd className="text-muted-foreground">{service.detail}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-10">
        <h2 className="font-medium">Pages that land next</h2>
        <dl className="mt-3 divide-y divide-border border-y border-border">
          {upcoming.map((page) => (
            <div key={page.name} className="flex gap-4 py-2.5">
              <dt className="w-24 shrink-0 leading-5">{page.name}</dt>
              <dd className="text-muted-foreground">{page.detail}</dd>
            </div>
          ))}
        </dl>
      </section>

      <p className="mt-10 text-muted-foreground">
        Build order is in{" "}
        <code className="font-mono text-xs text-foreground">docs/PROMPTS.md</code>. Every
        design decision behind it is in{" "}
        <code className="font-mono text-xs text-foreground">docs/DECISIONS.md</code>.
      </p>
    </main>
  );
}
