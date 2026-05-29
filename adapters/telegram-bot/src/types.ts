export type Platform = "telegram";

export interface InboundMessageEnvelope {
  trace_id: string;
  platform: Platform;
  external_workspace_id: string;
  channel_id: string;
  user_id: string;
  message_id: string;
  text: string;
  thread_id?: string | null;
}

export interface IngestAcceptedResponse {
  trace_id: string;
  chat_event_id: string;
  status: "accepted";
}

export interface OutboundMessageEnvelope {
  trace_id: string;
  tenant_id: string;
  direction: "outbound";
  platform: Platform;
  channel_id: string;
  user_id: string;
  reply_to_message_id: string;
  inbound_chat_event_id: string;
  text: string;
}

export interface TelegramUpdate {
  update_id?: number;
  message?: TelegramMessage;
}

export interface TelegramMessage {
  message_id: number;
  message_thread_id?: number;
  chat: {
    id: number | string;
  };
  from?: {
    id: number | string;
  };
  text?: string;
}
