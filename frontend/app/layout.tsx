import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Analyst Workspace",
  description: "A shared workspace for data, analysis, dashboards, and reports.",
};

export default function Layout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning><body><Providers>{children}</Providers></body></html>;
}
