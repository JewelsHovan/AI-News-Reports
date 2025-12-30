-- AI News Newsletter Subscribers Schema
-- Run with: wrangler d1 execute ai-news-subscribers --file=./schema.sql

DROP TABLE IF EXISTS subscribers;

CREATE TABLE subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  verification_token TEXT,
  verified INTEGER DEFAULT 0,
  active INTEGER DEFAULT 1,
  created_at INTEGER DEFAULT (unixepoch()),
  verified_at INTEGER
);

-- Index for fetching active, verified subscribers
CREATE INDEX idx_verified_active ON subscribers(verified, active);

-- Index for token lookup during verification
CREATE INDEX idx_verification_token ON subscribers(verification_token);

-- Index for email lookup
CREATE INDEX idx_email ON subscribers(email);
