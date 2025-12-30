# AI News Newsletter Config

This folder stores configuration files for the AI News email newsletter.

## Files

- `recipients.json`: List of recipients with `name`, `email`, `active`.
- `email_config.json`: Microsoft Graph and sender settings (no secrets).
- `sent_log_YYYY-MM-DD.txt`: Idempotency log (auto-created by the sender script).

## Azure AD App Registration (Microsoft Entra)

1. Create a new app registration in the Azure Portal.
2. Record the **Tenant ID** and **Client ID** and put them in `email_config.json`.
3. Under **API permissions**, add **Microsoft Graph** → **Delegated permissions** → `Mail.Send`.
4. Grant admin consent for the tenant.
5. Under **Authentication**, enable **Allow public client flows** if using device code flow.

### Optional: Client credentials flow

If you want app-only tokens:
- Create a **Client Secret** and store it in the macOS Keychain (see below).
- Ensure your app has **Application** permission `Mail.Send` and admin consent.
- Set `auth_flow` to `client_credentials` in `email_config.json`.

## Store the Client Secret in macOS Keychain

Use the configured service name (default: `ai-news-graph-api`).

```bash
security add-generic-password \
  -s "ai-news-graph-api" \
  -a "ai-news-graph-api" \
  -w "<CLIENT_SECRET>" \
  -U
```

The sender script will read it with:

```bash
security find-generic-password -s "ai-news-graph-api" -a "ai-news-graph-api" -w
```

## Launchd job

To load the scheduled job:

```bash
launchctl load -w ~/Library/LaunchAgents/com.ainews.newsletter.plist
```

To unload it:

```bash
launchctl unload -w ~/Library/LaunchAgents/com.ainews.newsletter.plist
```

## Quick test

```bash
uv run python .claude/skills/ai-news/scripts/send_newsletter.py \
  --dry-run --test-email you@example.com --verbose
```
