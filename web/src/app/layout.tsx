import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";

// Inter at a 14px base, per the UI brief. next/font exposes it as `--font-sans`,
// which is the variable shadcn's theme layer reads — the scaffold pointed that
// variable at itself, so nothing resolved and type fell back to the browser default.
const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

// Tabular figures for token counts, costs, and latencies on the Agents page.
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SocialOps",
  description:
    "Multi-agent social media command center. Triage, draft, and approve replies across brands.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning on the two document-level elements only.
    //
    // Extensions stamp attributes onto <html> and <body> before React hydrates
    // — Bitdefender's `bis_register`, a `__processed_<uuid>__` marker, and the
    // `bis_skin_checked` it puts on every div. React compares the server HTML
    // against a DOM that has already been edited and reports a mismatch it
    // cannot patch, which buries real hydration bugs in noise on a developer's
    // machine and in a screen-share.
    //
    // It suppresses exactly one level, deliberately: React does not cascade it,
    // and it should not be pushed down onto application markup, where a genuine
    // mismatch (a locale date, a Math.random key) is a bug we need to see. The
    // div-level warnings from the same extension have no code fix; check the
    // console in a clean profile before treating one as ours.
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
