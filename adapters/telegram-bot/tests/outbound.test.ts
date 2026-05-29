import { describe, expect, it, vi } from "vitest";

import {
  deliverOutboundMessage,
  ensureOutboundConsumerGroup,
  parseOutboundMessage,
  readOutboundMessages,
} from "../src/outbound.js";

const payload = {
  trace_id: "11111111-1111-4111-8111-111111111111",
  tenant_id: "22222222-2222-4222-8222-222222222222",
  direction: "outbound",
  platform: "telegram",
  channel_id: "-100123",
  user_id: "99",
  reply_to_message_id: "42",
  inbound_chat_event_id: "33333333-3333-4333-8333-333333333333",
  text: "stub:hello"
} as const;

const receiptKey = "telegram:outbound:sent:local:tenant:outbound:telegram:telegram:1-0";

function redisClient(overrides: Partial<ReturnType<typeof baseRedisClient>> = {}) {
  return {
    ...baseRedisClient(),
    ...overrides,
  };
}

function baseRedisClient() {
  return {
    get: vi.fn(async (): Promise<string | null> => null),
    set: vi.fn(async () => undefined),
    xAck: vi.fn(async () => 1),
  };
}

describe("outbound delivery", () => {
  it("parses outbound stream payloads", () => {
    const envelope = parseOutboundMessage({
      id: "1-0",
      fields: { payload: JSON.stringify(payload) }
    });

    expect(envelope).toEqual(payload);
  });

  it("sends Telegram replies and ACKs only after success", async () => {
    const telegram = { sendMessage: vi.fn(async () => ({})) };
    const redis = redisClient();
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);

    try {
      await deliverOutboundMessage(
        { id: "1-0", fields: { payload: JSON.stringify(payload) } },
        {
          stream: "local:tenant:outbound:telegram",
          group: "telegram",
          telegram,
          redis,
          receiptStore: redis
        }
      );

      expect(telegram.sendMessage).toHaveBeenCalledWith("-100123", "stub:hello", {
        reply_parameters: { message_id: 42 }
      });
      expect(redis.xAck).toHaveBeenCalledWith("local:tenant:outbound:telegram", "telegram", "1-0");
      expect(redis.set).toHaveBeenCalledWith(
        receiptKey,
        expect.stringContaining(payload.trace_id),
        604800
      );
      expect(info).toHaveBeenCalledWith("telegram_outbound_send_succeeded", {
        stream_id: "1-0",
        trace_id: payload.trace_id,
        tenant_id: payload.tenant_id,
        platform: "telegram"
      });
      expect(JSON.stringify(info.mock.calls)).not.toContain(payload.text);
    } finally {
      info.mockRestore();
    }
  });

  it("does not ACK when Telegram send fails", async () => {
    const telegram = {
      sendMessage: vi.fn(async () => {
        throw new Error("telegram failed");
      })
    };
    const redis = redisClient();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);

    try {
      await expect(
        deliverOutboundMessage(
          { id: "1-0", fields: { payload: JSON.stringify(payload) } },
          {
            stream: "local:tenant:outbound:telegram",
            group: "telegram",
            telegram,
            redis,
            receiptStore: redis
          }
        )
      ).rejects.toThrow("telegram failed");

      expect(redis.xAck).not.toHaveBeenCalled();
      expect(redis.set).not.toHaveBeenCalled();
      expect(warn).toHaveBeenCalledWith("telegram_outbound_send_failed", {
        stream_id: "1-0",
        trace_id: payload.trace_id,
        tenant_id: payload.tenant_id,
        platform: "telegram",
        error_class: "Error"
      });
      expect(JSON.stringify(warn.mock.calls)).not.toContain(payload.text);
    } finally {
      warn.mockRestore();
    }
  });

  it("logs parsed outbound context when ACK fails after send", async () => {
    const telegram = { sendMessage: vi.fn(async () => ({})) };
    const redis = redisClient({
      xAck: vi.fn(async () => {
        throw new Error("redis failed");
      })
    });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);

    try {
      await expect(
        deliverOutboundMessage(
          { id: "1-0", fields: { payload: JSON.stringify(payload) } },
          {
            stream: "local:tenant:outbound:telegram",
            group: "telegram",
            telegram,
            redis,
            receiptStore: redis
          }
        )
      ).rejects.toThrow("redis failed");

      expect(redis.set).toHaveBeenCalledWith(
        receiptKey,
        expect.stringContaining(payload.trace_id),
        604800
      );
      expect(warn).toHaveBeenCalledWith("telegram_outbound_ack_failed_after_send", {
        stream_id: "1-0",
        trace_id: payload.trace_id,
        tenant_id: payload.tenant_id,
        platform: "telegram",
        delivery_receipt_recorded: "true",
        error_class: "Error"
      });
      expect(JSON.stringify(warn.mock.calls)).not.toContain(payload.text);
    } finally {
      warn.mockRestore();
    }
  });

  it("skips Telegram send and ACKs when a delivery receipt already exists", async () => {
    const telegram = { sendMessage: vi.fn(async () => ({})) };
    const redis = redisClient({
      get: vi.fn(async () => "sent")
    });
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);

    try {
      await deliverOutboundMessage(
        { id: "1-0", fields: { payload: JSON.stringify(payload) } },
        {
          stream: "local:tenant:outbound:telegram",
          group: "telegram",
          telegram,
          redis,
          receiptStore: redis
        }
      );

      expect(telegram.sendMessage).not.toHaveBeenCalled();
      expect(redis.xAck).toHaveBeenCalledWith("local:tenant:outbound:telegram", "telegram", "1-0");
      expect(info).toHaveBeenCalledWith("telegram_outbound_ack_succeeded_after_receipt", {
        stream_id: "1-0",
        trace_id: payload.trace_id,
        tenant_id: payload.tenant_id,
        platform: "telegram"
      });
      expect(JSON.stringify(info.mock.calls)).not.toContain(payload.text);
    } finally {
      info.mockRestore();
    }
  });

  it("does not send when the delivery receipt check fails", async () => {
    const telegram = { sendMessage: vi.fn(async () => ({})) };
    const redis = redisClient({
      get: vi.fn(async () => {
        throw new Error("redis failed");
      })
    });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);

    try {
      await expect(
        deliverOutboundMessage(
          { id: "1-0", fields: { payload: JSON.stringify(payload) } },
          {
            stream: "local:tenant:outbound:telegram",
            group: "telegram",
            telegram,
            redis,
            receiptStore: redis
          }
        )
      ).rejects.toThrow("redis failed");

      expect(telegram.sendMessage).not.toHaveBeenCalled();
      expect(redis.xAck).not.toHaveBeenCalled();
      expect(warn).toHaveBeenCalledWith("telegram_outbound_receipt_check_failed", {
        stream_id: "1-0",
        trace_id: payload.trace_id,
        tenant_id: payload.tenant_id,
        platform: "telegram",
        error_class: "Error"
      });
      expect(JSON.stringify(warn.mock.calls)).not.toContain(payload.text);
    } finally {
      warn.mockRestore();
    }
  });

  it("creates the outbound consumer group if it is missing", async () => {
    const redis = { xGroupCreate: vi.fn(async () => "OK") };

    await ensureOutboundConsumerGroup(redis, "local:tenant:outbound:telegram", "telegram");

    expect(redis.xGroupCreate).toHaveBeenCalledWith(
      "local:tenant:outbound:telegram",
      "telegram",
      "0",
      { MKSTREAM: true }
    );
  });

  it("keeps startup idempotent when the outbound consumer group already exists", async () => {
    const redis = {
      xGroupCreate: vi.fn(async () => {
        throw new Error("BUSYGROUP Consumer Group name already exists");
      })
    };

    await expect(
      ensureOutboundConsumerGroup(redis, "local:tenant:outbound:telegram", "telegram")
    ).resolves.toBeUndefined();
  });

  it("reads pending outbound messages for the current consumer", async () => {
    const redis = {
      xReadGroup: vi.fn(async () => [
        {
          messages: [
            {
              id: "1-0",
              message: { payload: JSON.stringify(payload) }
            }
          ]
        }
      ])
    };

    const messages = await readOutboundMessages(
      redis,
      "local:tenant:outbound:telegram",
      "telegram",
      "telegram-1",
      "0"
    );

    expect(redis.xReadGroup).toHaveBeenCalledWith(
      "telegram",
      "telegram-1",
      [{ key: "local:tenant:outbound:telegram", id: "0" }],
      { COUNT: 10 }
    );
    expect(messages).toEqual([{ id: "1-0", fields: { payload: JSON.stringify(payload) } }]);
  });
});
