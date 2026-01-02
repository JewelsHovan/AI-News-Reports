export interface Env {
  DB: D1Database;
  ARCHIVE_KV: KVNamespace;
  ARCHIVE_R2: R2Bucket;
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

// Archive types
export interface ReportMeta {
  id: string;                    // e.g., "2026-01-02_20260102T081220Z"
  date_range_start: string;      // "2025-12-31"
  date_range_end: string;        // "2026-01-02"
  generated_at: string;          // ISO timestamp
  title: string;                 // "AI News Digest: Dec 31 - Jan 2"
  summary: string;               // Brief description
  r2_key: string;                // "reports/2026-01-02_20260102T081220Z.html"
  days: number;
  total_items: number;
}

export interface ArchiveIndex {
  reports: ReportMeta[];
  updated_at: string;
}
