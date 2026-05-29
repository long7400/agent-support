import { describe, expect, it } from "vitest";

import { normalizeTelegramUpdate } from "../src/normalize.js";

describe("normalizeTelegramUpdate", () => {
  it("normalizes Telegram text messages to internal envelopes", () => {
    const envelope = normalizeTelegramUpdate(
      {
        update_id: 1,
        message: {
          message_id: 42,
          message_thread_id: 7,
          chat: { id: -100123 },
          from: { id: 99 },
          text: "hello"
        }
      },
      {
        externalWorkspaceId: "sandbox-workspace",
        traceIdFactory: () => "11111111-1111-4111-8111-111111111111"
      }
    );

    expect(envelope).toEqual({
      trace_id: "11111111-1111-4111-8111-111111111111",
      platform: "telegram",
      external_workspace_id: "sandbox-workspace",
      channel_id: "-100123",
      user_id: "99",
      message_id: "42",
      text: "hello",
      thread_id: "7"
    });
  });

  it("ignores non-text updates", () => {
    const envelope = normalizeTelegramUpdate(
      {
        update_id: 1,
        message: {
          message_id: 42,
          chat: { id: -100123 },
          from: { id: 99 }
        }
      },
      { externalWorkspaceId: "sandbox-workspace" }
    );

    expect(envelope).toBeNull();
  });

  it("does not include trusted tenant ids", () => {
    const envelope = normalizeTelegramUpdate(
      {
        update_id: 1,
        message: {
          message_id: 42,
          chat: { id: -100123 },
          from: { id: 99 },
          text: "hello"
        }
      },
      { externalWorkspaceId: "sandbox-workspace", traceIdFactory: () => "trace-id" }
    );

    expect(envelope).not.toHaveProperty("tenant_id");
  });
});
