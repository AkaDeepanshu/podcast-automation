import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink shadow-none transition-colors outline-none",
        "placeholder:text-muted-foreground",
        "hover:border-ink/20",
        "focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-paper-deep/60 disabled:opacity-50",
        "aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20",
        "file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export { Input }
