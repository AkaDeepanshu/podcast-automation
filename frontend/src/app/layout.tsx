import type { Metadata } from "next";
import { Figtree, Fraunces } from "next/font/google";
import { AppShell } from "@/components/AppShell";
import { ToastProvider } from "@/components/Toaster";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
});

const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Studio — Podcast Automation",
  description: "Create and manage AI podcast episodes",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${fraunces.variable} ${figtree.variable} h-full`}>
      <body className="relative min-h-full antialiased">
        <div className="relative z-10">
          <ToastProvider>
            <AppShell>{children}</AppShell>
          </ToastProvider>
        </div>
      </body>
    </html>
  );
}
