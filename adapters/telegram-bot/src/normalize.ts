import { randomUUID } from "node:crypto";

import type { InboundMessageEnvelope, TelegramUpdate } from "./types.js";

interface NormalizeOptions {
  externalWorkspaceId: string;
  traceIdFactory?: () => string;
}

export function normalizeTelegramUpdate(
  update: TelegramUpdate,
  options: NormalizeOptions,
): InboundMessageEnvelope | null {
  const message = update.message;
  if (message === undefined || message.text === undefined || message.text === "") {
    return null;
  }
  if (message.from?.id === undefined) {
    return null;
  }
  return {
    trace_id: (options.traceIdFactory ?? randomUUID)(),
    platform: "telegram",
    external_workspace_id: options.externalWorkspaceId,
    channel_id: String(message.chat.id),
    user_id: String(message.from.id),
    message_id: String(message.message_id),
    text: message.text,
    ...(message.message_thread_id === undefined
      ? {}
      : { thread_id: String(message.message_thread_id) }),
  };
}
