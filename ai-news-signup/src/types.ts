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
  title: string;                 // "Julien's AI Brief: Dec 31 - Jan 2"
  summary: string;               // Brief description
  r2_key: string;                // "reports/2026-01-02_20260102T081220Z.html"
  days: number;
  total_items: number;
  // Listing fields for archive cards (absent on older entries)
  issue_title?: string;          // Editorial title, e.g. "Le Chonk and a $40B chip bet"
  issue_number?: number;         // Sequential, shared by duplicate uploads of a range
  headline?: string;             // Top story #1
  tldr?: string;                 // First sentences of the executive summary
  top_stories?: string[];        // Up to 5 top-story titles
  tags?: string[];               // Up to 3 topic tags, e.g. "Agents"
}

export type ReportListing = Pick<ReportMeta, 'issue_title' | 'issue_number' | 'headline' | 'tldr' | 'top_stories' | 'tags'>;

export interface ArchiveIndex {
  reports: ReportMeta[];
  updated_at: string;
}
