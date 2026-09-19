"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Episodes" },
  { href: "/topics", label: "Topics" },
  { href: "/config", label: "Config" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16 pt-8 sm:px-8">
      <header className="animate-rise mb-10 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-accent">
            Podcast Automation
          </p>
          <Link href="/" className="font-serif text-4xl tracking-tight text-ink sm:text-5xl">
            Studio
          </Link>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
            Script, voice, and assemble episodes from one place.
          </p>
        </div>
        <nav className="flex items-center gap-1 border-b border-line pb-px">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative px-4 py-2 text-sm transition-colors ${
                  active ? "text-ink" : "text-muted hover:text-ink-soft"
                }`}
              >
                {item.label}
                {active && (
                  <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-accent" />
                )}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
