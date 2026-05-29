import { describe, expect, it, vi } from "vitest";

import { ControlPlaneClient } from "../src/client.js";
import type { InboundMessageEnvelope } from "../src/types.js";

const envelope: InboundMessageEnvelope = {
  trace_id: "11111111-1111-4111-8111-111111111111",
  platform: "telegram",
  external_workspace_id: "sandbox-workspace",
  channel_id: "channel-a",
  user_id: "user-a",
  message_id: "message-a",
  text: "hello"
};

describe("ControlPlaneClient", () => {
  it("posts internal ingest with adapter credential and trace id", async () => {
    const fetchFn = vi.fn(async () => new Response("{}", { status: 202 }));
    const client = new ControlPlaneClient({
      baseUrl: "http://control.test/",
      adapterToken: "local-adapter-token",
      timeoutMs: 1000,
      fetchFn
    });

    await client.ingest(envelope);

    expect(fetchFn).toHaveBeenCalledWith(
      "http://control.test/internal/messages/ingest",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "x-adapter-token": "local-adapter-token",
          "x-trace-id": envelope.trace_id
        }),
        body: JSON.stringify(envelope)
      })
    );
  });
});
