/**
 * SSE consumer for POST /api/runs/stream.
 *
 * Uses native EventSource-like pattern via fetch + ReadableStream since
 * EventSource only supports GET. We parse SSE lines manually.
 */

import type { AnalyzeRequest } from "./client";

export interface SSEEvent {
  event: string;
  data: string;
}

export type SSECallback = (evt: SSEEvent) => void;

/**
 * Open an SSE stream to the analyze endpoint.
 * Returns an AbortController so the caller can cancel.
 */
export function streamAnalyze(
  req: AnalyzeRequest,
  onEvent: SSECallback,
  onError: (err: Error) => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch("/api/runs/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "Unknown error");
        onError(new Error(`SSE ${res.status}: ${text}`));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError(new Error("No response body"));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "message";
      let currentData = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            currentData = line.slice(5).trim();
          } else if (line === "") {
            // Empty line = end of SSE event
            if (currentData) {
              onEvent({ event: currentEvent, data: currentData });
            }
            currentEvent = "message";
            currentData = "";
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError(err as Error);
      }
    }
  })();

  return controller;
}
