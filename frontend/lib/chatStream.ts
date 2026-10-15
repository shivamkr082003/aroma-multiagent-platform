import { API } from "@/lib/auth";

export type Source = {
  id: number;
  type: "document" | "web";
  title: string;
  page?: number | null;
  snippet?: string;
  url?: string;
};

// Mirrors Agent.agent.achat_stream on the backend.
export type StreamEvent =
  | { type: "status"; label: string }
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "reset" }
  | { type: "done"; response: string; sources: Source[] }
  | { type: "error"; message: string };

export class UnauthorizedError extends Error {}

/** POST a chat message and call onEvent for each Server-Sent Event until the stream ends. */
export async function streamChat(
  body: { message: string; session_id: string; file_id?: string },
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  // fetch, not axios: axios can't read a response body incrementally in the browser.
  const response = await fetch(`${API}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 401) throw new UnauthorizedError();
  if (!response.ok || !response.body) throw new Error(`Chat request failed (${response.status})`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Events are separated by a blank line; a network chunk may hold several or half of one.
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(JSON.parse(data) as StreamEvent);
    }
  }
}
