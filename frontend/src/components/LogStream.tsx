"use client";

import { useEffect, useRef, useState } from "react";
import { wsLogsUrl } from "@/lib/api";

type LogLine = {
  level: string;
  msg: string;
  ts: number | null;
  replay?: boolean;
};

const LEVEL_COLOR: Record<string, string> = {
  INFO: "text-[#9fceb8]",
  WARNING: "text-[#e6c27a]",
  ERROR: "text-[#f0a39a]",
  DEBUG: "text-[#8aa0b5]",
};

type Props = {
  jobId: string;
};

export function LogStream({ jobId }: Props) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    setLines([]);
    setError(null);
    let closed = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(wsLogsUrl(jobId));

      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as LogLine;
          setLines((prev) => [...prev, payload]);
        } catch {
          setLines((prev) => [
            ...prev,
            { level: "INFO", msg: String(event.data), ts: null },
          ]);
        }
      };

      ws.onerror = () => {
        setError("Log stream connection error");
      };

      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        attempt += 1;
        const delay = Math.min(8000, 600 * attempt);
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [jobId]);

  useEffect(() => {
    if (stickToBottom.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines]);

  function onScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottom.current = distance < 48;
  }

  return (
    <div className="rounded-lg bg-[#121714] p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-end gap-3">
        <span
          className={`text-xs font-semibold uppercase tracking-[0.14em] ${
            connected ? "text-[#9fceb8]" : "text-[#e6c27a]"
          }`}
        >
          {connected ? "Connected" : "Reconnecting…"}
        </span>
      </div>

      {error && (
        <p className="mb-2 text-xs text-[#f0a39a]">{error}</p>
      )}

      <div
        onScroll={onScroll}
        className="h-72 overflow-y-auto rounded-lg bg-[#0c100e] px-3 py-3 font-mono text-[12px] leading-5 sm:h-80"
      >
        {lines.length === 0 ? (
          <p className="text-[#6a736c]">Waiting for log output…</p>
        ) : (
          lines.map((line, i) => (
            <div key={`${i}-${line.ts ?? "r"}`} className="whitespace-pre-wrap break-words">
              <span className={LEVEL_COLOR[line.level] ?? "text-[#c5cdc7]"}>
                [{line.level}]
              </span>{" "}
              <span className="text-[#d7ddd8]">{line.msg}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
