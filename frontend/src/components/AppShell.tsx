"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Episodes" },
  { href: "/topics", label: "Topics" },
  { href: "/automation", label: "Automation" },
  { href: "/config", label: "Config" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const onScroll = () => setCompact(window.scrollY > 16);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen w-full">
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-40 border-b transition-[padding,background-color,border-color,box-shadow] duration-300 ease-out",
          compact
            ? "border-line/80 bg-surface/90 py-2 shadow-[0_8px_30px_rgba(22,27,24,0.06)] backdrop-blur-xl"
            : "border-transparent bg-transparent py-3.5",
        )}
      >
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
          <Link href="/" className="group min-w-0">
            <p
              className={cn(
                "font-semibold uppercase tracking-[0.2em] text-accent transition-all duration-300",
                compact
                  ? "mb-0 h-0 overflow-hidden text-[9px] opacity-0"
                  : "mb-1 text-[10px]",
              )}
            >
              Podcast Automation
            </p>
            <span
              className={cn(
                "block font-serif tracking-tight text-ink transition-all duration-300",
                compact ? "text-xl sm:text-2xl" : "text-2xl sm:text-[1.75rem]",
              )}
            >
              Studio
            </span>
          </Link>

          <nav
            className={cn(
              "flex shrink-0 items-center rounded-full border border-line/70 bg-surface/80 p-1 shadow-[var(--shadow)] backdrop-blur-md transition-transform duration-300",
              compact && "scale-[0.97]",
            )}
          >
            {NAV.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-xs font-semibold transition-colors sm:px-3.5 sm:text-sm",
                    active
                      ? "bg-accent !text-white shadow-sm hover:!text-white"
                      : "text-muted-foreground hover:bg-paper-deep/80 hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <div
        className={cn(
          "mx-auto flex w-full max-w-6xl flex-col px-5 pb-20 sm:px-8 transition-[padding] duration-300",
          compact ? "pt-16" : "pt-20 sm:pt-24",
        )}
      >
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
