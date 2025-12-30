export interface Env {
  DB: D1Database;
  TURNSTILE_SECRET_KEY: string;
  ADMIN_API_SECRET: string;
  HMAC_SECRET: string;
  MS_GRAPH_CLIENT_ID: string;
  MS_GRAPH_CLIENT_SECRET: string;
  MS_GRAPH_TENANT_ID: string;
  SENDER_EMAIL: string;
  WORKER_URL: string;
}

export interface Subscriber {
  id: number;
  email: string;
  name: string | null;
  verification_token: string | null;
  verified: number;
  active: number;
  created_at: number;
  verified_at: number | null;
}

export interface SubscribeRequest {
  email: string;
  name?: string;
  turnstileToken: string;
}

export interface RecipientEntry {
  name: string | null;
  email: string;
  active: boolean;
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}
