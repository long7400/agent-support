import type { OutboundMessageEnvelope } from "./types.js";

export interface RedisStreamMessage {
  id: string;
  fields: Record<string, string>;
}

export type ReadGroupId = "0" | ">";

export interface RedisReadGroupClient {
  xReadGroup(
    group: string,
    consumer: string,
    streams: Array<{ key: string; id: ReadGroupId }>,
    options: { COUNT: number; BLOCK?: number }
  ): Promise<unknown>;
}

export interface TelegramSender {
  sendMessage(
    chatId: string,
    text: string,
    options?: { reply_parameters?: { message_id: number } }
  ): Promise<unknown>;
}

export interface AckClient {
  xAck(stream: string, group: string, id: string): Promise<number>;
}

export interface DeliveryReceiptClient {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, ttlSeconds: number): Promise<void>;
}

export interface ConsumerGroupClient {
  xGroupCreate(
    stream: string,
    group: string,
    id: string,
    options: { MKSTREAM: true }
  ): Promise<unknown>;
}

export interface DeliverOutboundOptions {
  stream: string;
  group: string;
  telegram: TelegramSender;
  redis: AckClient;
  receiptStore?: DeliveryReceiptClient;
  receiptTtlSeconds?: number;
}

const DEFAULT_RECEIPT_TTL_SECONDS = 7 * 24 * 60 * 60;

export function parseOutboundMessage(message: RedisStreamMessage): OutboundMessageEnvelope {
  const payload = message.fields.payload;
  if (payload === undefined) {
    throw new Error("outbound message payload is missing");
  }
  return JSON.parse(payload) as OutboundMessageEnvelope;
}

export async function deliverOutboundMessage(
  message: RedisStreamMessage,
  options: DeliverOutboundOptions
): Promise<void> {
  const envelope = parseOutboundMessage(message);
  const logContext = {
    stream_id: message.id,
    trace_id: envelope.trace_id,
    tenant_id: envelope.tenant_id,
    platform: envelope.platform
  };
  const replyId = Number.parseInt(envelope.reply_to_message_id, 10);
  const sendOptions = Number.isSafeInteger(replyId)
    ? { reply_parameters: { message_id: replyId } }
    : undefined;
  const receiptKey =
    options.receiptStore === undefined
      ? undefined
      : deliveryReceiptKey(options.stream, options.group, message.id);
  if (options.receiptStore !== undefined && receiptKey !== undefined) {
    let hasReceipt: boolean;
    try {
      hasReceipt = (await options.receiptStore.get(receiptKey)) !== null;
    } catch (error: unknown) {
      logOutboundFailure("telegram_outbound_receipt_check_failed", logContext, error);
      throw error;
    }
    if (hasReceipt) {
      await ackAfterKnownSend(message, options, logContext, "telegram_outbound_ack_failed_after_receipt");
      console.info("telegram_outbound_ack_succeeded_after_receipt", logContext);
      return;
    }
  }
  try {
    await options.telegram.sendMessage(envelope.channel_id, envelope.text, sendOptions);
  } catch (error: unknown) {
    logOutboundFailure("telegram_outbound_send_failed", logContext, error);
    throw error;
  }
  let deliveryReceiptRecorded = false;
  if (options.receiptStore !== undefined && receiptKey !== undefined) {
    deliveryReceiptRecorded = await recordDeliveryReceipt(
      options.receiptStore,
      receiptKey,
      envelope,
      message.id,
      options.receiptTtlSeconds ?? DEFAULT_RECEIPT_TTL_SECONDS,
      logContext
    );
  }
  await ackAfterKnownSend(
    message,
    options,
    { ...logContext, delivery_receipt_recorded: String(deliveryReceiptRecorded) },
    "telegram_outbound_ack_failed_after_send"
  );
  console.info("telegram_outbound_send_succeeded", logContext);
}

async function ackAfterKnownSend(
  message: RedisStreamMessage,
  options: DeliverOutboundOptions,
  logContext: Record<string, string>,
  failureEvent: string
): Promise<void> {
  try {
    await options.redis.xAck(options.stream, options.group, message.id);
  } catch (error: unknown) {
    logOutboundFailure(failureEvent, logContext, error);
    throw error;
  }
}

async function recordDeliveryReceipt(
  receiptStore: DeliveryReceiptClient,
  receiptKey: string,
  envelope: OutboundMessageEnvelope,
  streamId: string,
  ttlSeconds: number,
  logContext: Record<string, string>
): Promise<boolean> {
  try {
    await receiptStore.set(
      receiptKey,
      JSON.stringify({
        trace_id: envelope.trace_id,
        tenant_id: envelope.tenant_id,
        platform: envelope.platform,
        stream_id: streamId,
      }),
      ttlSeconds
    );
    return true;
  } catch (error: unknown) {
    logOutboundFailure("telegram_outbound_receipt_failed_after_send", logContext, error);
    return false;
  }
}

export async function ensureOutboundConsumerGroup(
  redis: ConsumerGroupClient,
  stream: string,
  group: string
): Promise<void> {
  try {
    await redis.xGroupCreate(stream, group, "0", { MKSTREAM: true });
  } catch (error: unknown) {
    if (isBusyGroupError(error)) {
      return;
    }
    throw error;
  }
}

export async function readOutboundMessages(
  redis: RedisReadGroupClient,
  stream: string,
  group: string,
  consumer: string,
  id: ReadGroupId,
  blockMs?: number
): Promise<RedisStreamMessage[]> {
  const options = blockMs === undefined ? { COUNT: 10 } : { COUNT: 10, BLOCK: blockMs };
  const response = await redis.xReadGroup(group, consumer, [{ key: stream, id }], options);
  if (!Array.isArray(response)) {
    return [];
  }
  const messages: RedisStreamMessage[] = [];
  for (const streamResponse of response) {
    if (!isStreamResponse(streamResponse)) {
      continue;
    }
    for (const message of streamResponse.messages) {
      messages.push({
        id: message.id,
        fields: message.message,
      });
    }
  }
  return messages;
}

function isBusyGroupError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("BUSYGROUP");
}

function deliveryReceiptKey(stream: string, group: string, id: string): string {
  return `telegram:outbound:sent:${stream}:${group}:${id}`;
}

function logOutboundFailure(event: string, context: Record<string, string>, error: unknown): void {
  console.warn(event, {
    ...context,
    error_class: error instanceof Error ? error.name : "UnknownError"
  });
}

interface ReadGroupStreamResponse {
  messages: Array<{
    id: string;
    message: Record<string, string>;
  }>;
}

function isStreamResponse(value: unknown): value is ReadGroupStreamResponse {
  if (typeof value !== "object" || value === null || !("messages" in value)) {
    return false;
  }
  const messages = (value as { messages: unknown }).messages;
  return Array.isArray(messages) && messages.every(isRawMessage);
}

function isRawMessage(value: unknown): value is { id: string; message: Record<string, string> } {
  if (typeof value !== "object" || value === null || !("id" in value) || !("message" in value)) {
    return false;
  }
  const id = (value as { id: unknown }).id;
  const message = (value as { message: unknown }).message;
  return typeof id === "string" && isRecordOfStrings(message);
}

function isRecordOfStrings(value: unknown): value is Record<string, string> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  return Object.values(value).every((item) => typeof item === "string");
}
