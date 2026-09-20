import { cn } from "@/lib/utils";

type PageShellProps = {
  children: React.ReactNode;
  /** wide = full AppShell width; form = max-w-3xl centered */
  variant?: "wide" | "form";
  className?: string;
};

export function PageShell({
  children,
  variant = "wide",
  className,
}: PageShellProps) {
  return (
    <div
      className={cn(
        "animate-rise flex w-full flex-col gap-8",
        variant === "form" && "mx-auto max-w-3xl",
        className,
      )}
    >
      {children}
    </div>
  );
}
