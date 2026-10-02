import { useEffect, useRef, useState } from "react";

export type LiveCommand = { action: string; params: Record<string, unknown> };

/** Registers one real live-control session for this open tab, then
 * consumes its real SSE command stream via fetch + a manual parser
 * (not the native EventSource API, which cannot send the real
 * Authorization header the backend requires). Every command the
 * backend relays reaches onCommand in the real order it was sent.
 */
export function useLiveAgentSession(
  viewerType: "volume" | "channel_volume" | "detection" | "tracking",
  authToken: string | undefined,
  onCommand: (command: LiveCommand) => void,
): string | null {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const onCommandRef = useRef(onCommand);
  onCommandRef.current = onCommand;

  useEffect(() => {
    if (!authToken) return;
    let disposed = false;
    const controller = new AbortController();

    async function run() {
      const headers = { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` };
      const registerResponse = await fetch("/api/studio/live-sessions", {
        method: "POST",
        headers,
        body: JSON.stringify({ viewer_type: viewerType }),
      });
      if (!registerResponse.ok || disposed) return;
      const { session_id: id } = await registerResponse.json();
      if (disposed) return;
      setSessionId(id);

      const eventsResponse = await fetch(`/api/studio/live-sessions/${id}/events`, {
        headers: { Authorization: `Bearer ${authToken}` },
        signal: controller.signal,
      });
      if (!eventsResponse.ok || !eventsResponse.body) return;
      const reader = eventsResponse.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!disposed) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const event of events) {
          const dataLine = event.split("\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue; // a heartbeat comment line, not a real command
          onCommandRef.current(JSON.parse(dataLine.slice("data: ".length)));
        }
      }
    }

    run().catch((error) => {
      if (!disposed && error?.name !== "AbortError") {
        // A real stream drop (network hiccup, tab backgrounded): the
        // live-control channel is best-effort, so this fails silently
        // rather than disrupting the viewer the person is looking at.
      }
    });

    return () => {
      disposed = true;
      controller.abort();
    };
  }, [viewerType, authToken]);

  return sessionId;
}
