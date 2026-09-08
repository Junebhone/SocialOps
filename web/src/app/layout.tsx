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
    <html lang="en">
      <body className={`${inter.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
