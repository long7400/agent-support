import type { InboundMessageEnvelope, IngestAcceptedResponse } from "./types.js";

export interface ControlPlaneClientOptions {
  baseUrl: string;
  adapterToken: string;
  timeoutMs: number;
  fetchFn?: typeof fetch;
}

export class ControlPlaneError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ControlPlaneError";
  }
}

export class ControlPlaneClient {
  private readonly baseUrl: string;
  private readonly adapterToken: string;
  private readonly timeoutMs: number;
  private readonly fetchFn: typeof fetch;

  constructor(options: ControlPlaneClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.adapterToken = options.adapterToken;
    this.timeoutMs = options.timeoutMs;
    this.fetchFn = options.fetchFn ?? fetch;
  }

  async ingest(envelope: InboundMessageEnvelope): Promise<IngestAcceptedResponse> {
    const response = await this.fetchFn(`${this.baseUrl}/internal/messages/ingest`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-adapter-token": this.adapterToken,
        "x-trace-id": envelope.trace_id,
      },
      body: JSON.stringify(envelope),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!response.ok) {
      throw new ControlPlaneError(`ingest failed with status ${response.status}`, response.status);
    }
    return (await response.json()) as IngestAcceptedResponse;
  }
}
