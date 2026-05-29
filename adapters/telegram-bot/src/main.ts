import { Bot } from "grammy";
import { createClient } from "redis";

import { ControlPlaneClient } from "./client.js";
import { loadConfig, type TelegramAdapterConfig } from "./config.js";
import { normalizeTelegramUpdate } from "./normalize.js";
import {
  deliverOutboundMessage,
  ensureOutboundConsumerGroup,
  readOutboundMessages,
} from "./outbound.js";
import type { RedisReadGroupClient, RedisStreamMessage } from "./outbound.js";

async function main(): Promise<void> {
  const config = loadConfig();
  const bot = new Bot(config.botToken);
  const client = new ControlPlaneClient({
    baseUrl: config.controlPlaneUrl,
    adapterToken: config.adapterToken,
    timeoutMs: config.requestTimeoutMs,
  });

  bot.on("message", async (ctx) => {
    const envelope = normalizeTelegramUpdate(ctx.update, {
      externalWorkspaceId: config.externalWorkspaceId,
    });
    if (envelope === null) {
      console.info("telegram_update_ignored", {
        update_id: ctx.update.update_id,
        reason: "unsupported_message",
      });
      return;
    }
    await client.ingest(envelope);
    console.info("telegram_update_ingested", {
      trace_id: envelope.trace_id,
      platform: envelope.platform,
      channel_id: envelope.channel_id,
      message_id: envelope.message_id,
    });
  });

  if (config.outboundStream !== "") {
    void runOutboundLoop(bot, config).catch((error: unknown) => {
      console.error("telegram_outbound_loop_failed", { error_class: (error as Error).name });
      process.exitCode = 1;
    });
  }

  await bot.start({
    onStart: ({ username }) => {
      console.info("telegram_adapter_started", { username });
    },
  });
}

async function runOutboundLoop(bot: Bot, config: TelegramAdapterConfig): Promise<void> {
  const redis = createClient({ url: config.redisUrl });
  await redis.connect();
  const reader = {
    xReadGroup: async (group, consumer, streams, options) =>
      redis.xReadGroup(group, consumer, streams, options),
  } satisfies RedisReadGroupClient;
  await ensureOutboundConsumerGroup(redis, config.outboundStream, config.outboundGroup);
  for (;;) {
    const pending = await readOutboundMessages(
      reader,
      config.outboundStream,
      config.outboundGroup,
      config.outboundConsumer,
      "0"
    );
    await deliverOutboundMessages(bot, redis, config, pending);
    const fresh = await readOutboundMessages(
      reader,
      config.outboundStream,
      config.outboundGroup,
      config.outboundConsumer,
      ">",
      5000
    );
    await deliverOutboundMessages(bot, redis, config, fresh);
  }
}

async function deliverOutboundMessages(
  bot: Bot,
  redis: {
    xAck(stream: string, group: string, id: string): Promise<number>;
    get(key: string): Promise<string | null>;
    set(key: string, value: string, options: { EX: number }): Promise<unknown>;
  },
  config: TelegramAdapterConfig,
  messages: RedisStreamMessage[]
): Promise<void> {
  for (const message of messages) {
    try {
      await deliverOutboundMessage(message, {
        stream: config.outboundStream,
        group: config.outboundGroup,
        telegram: bot.api,
        redis: {
          xAck: async (stream, group, id) => redis.xAck(stream, group, id),
        },
        receiptStore: {
          get: async (key) => redis.get(key),
          set: async (key, value, ttlSeconds) => {
            await redis.set(key, value, { EX: ttlSeconds });
          },
        },
      });
    } catch {
      // `deliverOutboundMessage` logs parsed envelope context and leaves the
      // entry pending for Redis retry.
    }
  }
}

main().catch((error: unknown) => {
  console.error("telegram_adapter_failed", { error_class: (error as Error).name });
  process.exitCode = 1;
});
