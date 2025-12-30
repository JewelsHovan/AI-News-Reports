/**
 * Generate HMAC-SHA256 token for email
 */
export async function generateHmacToken(secret: string, email: string): Promise<string> {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const messageData = encoder.encode(email.toLowerCase());

  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign('HMAC', cryptoKey, messageData);

  return Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Validate HMAC token for email (constant-time comparison)
 */
export async function validateHmacToken(
  secret: string,
  email: string,
  token: string
): Promise<boolean> {
  const expectedToken = await generateHmacToken(secret, email);

  if (expectedToken.length !== token.length) {
    return false;
  }

  let result = 0;
  for (let i = 0; i < expectedToken.length; i++) {
    result |= expectedToken.charCodeAt(i) ^ token.charCodeAt(i);
  }

  return result === 0;
}

/**
 * Generate random verification token (32 hex characters)
 */
export function generateVerificationToken(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
