interface TurnstileResponse {
  success: boolean;
  'error-codes'?: string[];
  challenge_ts?: string;
  hostname?: string;
}

/**
 * Validate Cloudflare Turnstile token
 */
export async function validateTurnstile(
  secretKey: string,
  token: string,
  remoteIp?: string
): Promise<{ success: boolean; error?: string }> {
  const formData = new URLSearchParams();
  formData.append('secret', secretKey);
  formData.append('response', token);
  if (remoteIp) {
    formData.append('remoteip', remoteIp);
  }

  try {
    const response = await fetch(
      'https://challenges.cloudflare.com/turnstile/v0/siteverify',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      }
    );

    if (!response.ok) {
      return { success: false, error: 'Turnstile verification service unavailable' };
    }

    const result: TurnstileResponse = await response.json();

    if (!result.success) {
      const errorCodes = result['error-codes']?.join(', ') || 'Unknown error';
      return { success: false, error: `Turnstile validation failed: ${errorCodes}` };
    }

    return { success: true };
  } catch (error) {
    console.error('Turnstile validation error:', error);
    return { success: false, error: 'Failed to validate Turnstile token' };
  }
}
