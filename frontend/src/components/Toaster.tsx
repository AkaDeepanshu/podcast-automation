"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ToastKind = "success" | "error" | "info";

export type ToastInput = {
  message: string;
  kind?: ToastKind;
  durationMs?: number;
};

type ToastItem = {
  id: string;
  message: string;
  kind: ToastKind;
};

type ToastContextValue = {
  toast: (input: ToastInput | string) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

let toastSeq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (input: ToastInput | string) => {
      const payload = typeof input === "string" ? { message: input } : input;
      const id = `t-${++toastSeq}-${Date.now()}`;
      const kind = payload.kind ?? "info";
      const durationMs = payload.durationMs ?? (kind === "error" ? 5600 : 3800);
      setItems((prev) => [...prev.slice(-4), { id, message: payload.message, kind }]);
      window.setTimeout(() => dismiss(id), durationMs);
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      toast,
      success: (message) => toast({ message, kind: "success" }),
      error: (message) => toast({ message, kind: "error" }),
      info: (message) => toast({ message, kind: "info" }),
    }),
    [toast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[80] flex flex-col items-end gap-2 p-4 sm:p-6"
        aria-live="polite"
      >
        {items.map((item) => (
          <div
            key={item.id}
            className={`pointer-events-auto animate-toast-in max-w-sm rounded-2xl border px-4 py-3 text-sm shadow-[var(--shadow)] backdrop-blur-md ${
              item.kind === "success"
                ? "border-[var(--ok)]/20 bg-[var(--ok-soft)]/95 text-[var(--ok)]"
                : item.kind === "error"
                  ? "border-[var(--danger)]/20 bg-[var(--danger-soft)]/95 text-[var(--danger)]"
                  : "border-line bg-surface/95 text-ink-soft"
            }`}
            role="status"
          >
            <div className="flex items-start gap-3">
              <p className="flex-1 leading-snug">{item.message}</p>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                className="shrink-0 text-xs opacity-60 transition hover:opacity-100"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
