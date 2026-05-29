export interface TelegramAdapterConfig {
  botToken: string;
  controlPlaneUrl: string;
  adapterToken: string;
  externalWorkspaceId: string;
  requestTimeoutMs: number;
  redisUrl: string;
  outboundStream: string;
  outboundGroup: string;
  outboundConsumer: string;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): TelegramAdapterConfig {
  const botToken = requiredEnv(env, "TELEGRAM_BOT_TOKEN");
  const adapterToken = requiredEnv(env, "AGENT_SUPPORT_ADAPTER_TOKEN");
  const externalWorkspaceId = requiredEnv(env, "TELEGRAM_EXTERNAL_WORKSPACE_ID");
  return {
    botToken,
    adapterToken,
    externalWorkspaceId,
    controlPlaneUrl: trimTrailingSlash(
      env.AGENT_SUPPORT_CONTROL_PLANE_URL ?? "http://127.0.0.1:8000",
    ),
    requestTimeoutMs: positiveInt(env.AGENT_SUPPORT_ADAPTER_TIMEOUT_MS, 5000),
    redisUrl: env.AGENT_SUPPORT_REDIS_URL ?? "redis://127.0.0.1:6379/0",
    outboundStream: env.TELEGRAM_OUTBOUND_STREAM ?? "",
    outboundGroup: env.TELEGRAM_OUTBOUND_GROUP ?? "telegram-sandbox",
    outboundConsumer: env.TELEGRAM_OUTBOUND_CONSUMER ?? "telegram-sandbox-1",
  };
}

function requiredEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name];
  if (value === undefined || value.trim() === "") {
    throw new ConfigError(`${name} is required`);
  }
  return value;
}

function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function positiveInt(rawValue: string | undefined, fallback: number): number {
  if (rawValue === undefined || rawValue.trim() === "") {
    return fallback;
  }
  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new ConfigError("AGENT_SUPPORT_ADAPTER_TIMEOUT_MS must be a positive integer");
  }
  return parsed;
}
