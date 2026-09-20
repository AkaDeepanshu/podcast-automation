import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function PageSkeleton({
  variant = "wide",
  rows = 4,
}: {
  variant?: "wide" | "form";
  rows?: number;
}) {
  return (
    <div
      className={cn(
        "flex w-full flex-col gap-8",
        variant === "form" && "mx-auto max-w-3xl",
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <Skeleton className="skeleton-shimmer h-8 w-48 rounded-lg" />
          <Skeleton className="skeleton-shimmer h-4 w-72 max-w-full rounded-md" />
        </div>
        <Skeleton className="skeleton-shimmer h-10 w-32 rounded-xl" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton
            key={i}
            className="skeleton-shimmer h-24 w-full rounded-[var(--radius)]"
          />
        ))}
      </div>
    </div>
  );
}

export function FormSkeleton() {
  return <PageSkeleton variant="form" rows={3} />;
}
