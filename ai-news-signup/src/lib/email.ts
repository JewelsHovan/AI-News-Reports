interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface MSGraphConfig {
  clientId: string;
  clientSecret: string;
  tenantId: string;
  senderEmail: string;
}

/**
 * Get OAuth2 access token using client credentials flow
 */
async function getAccessToken(config: MSGraphConfig): Promise<string> {
  const tokenUrl = `https://login.microsoftonline.com/${config.tenantId}/oauth2/v2.0/token`;

  const params = new URLSearchParams();
  params.append('client_id', config.clientId);
  params.append('client_secret', config.clientSecret);
  params.append('scope', 'https://graph.microsoft.com/.default');
  params.append('grant_type', 'client_credentials');

  const response = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to get access token: ${response.status} ${errorText}`);
  }

  const data: TokenResponse = await response.json();
  return data.access_token;
}

interface SendEmailOptions {
  to: string;
  toName?: string;
  subject: string;
  htmlBody: string;
}

/**
 * Send email via Microsoft Graph API
 */
export async function sendEmail(
  config: MSGraphConfig,
  options: SendEmailOptions
): Promise<{ success: boolean; error?: string }> {
  try {
    const accessToken = await getAccessToken(config);
    const sendMailUrl = `https://graph.microsoft.com/v1.0/users/${config.senderEmail}/sendMail`;

    const emailPayload = {
      message: {
        subject: options.subject,
        body: { contentType: 'HTML', content: options.htmlBody },
        toRecipients: [{
          emailAddress: { address: options.to, name: options.toName || options.to }
        }],
      },
      saveToSentItems: false,
    };

    const response = await fetch(sendMailUrl, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(emailPayload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('MS Graph sendMail error:', errorText);
      return { success: false, error: `Failed to send email: ${response.status}` };
    }

    return { success: true };
  } catch (error) {
    console.error('Email sending error:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown email error',
    };
  }
}

/**
 * Send verification email to new subscriber
 */
export async function sendVerificationEmail(
  config: MSGraphConfig,
  workerUrl: string,
  recipientEmail: string,
  recipientName: string | null,
  verificationToken: string
): Promise<{ success: boolean; error?: string }> {
  const verifyUrl = `${workerUrl}/verify?token=${verificationToken}`;

  const htmlBody = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 24px;">AI News Weekly</h1>
  </div>
  <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
    <h2 style="margin-top: 0;">Confirm your subscription</h2>
    <p>Hi${recipientName ? ` ${recipientName}` : ''},</p>
    <p>Thanks for subscribing to AI News Weekly! Click below to confirm:</p>
    <p style="text-align: center; margin: 30px 0;">
      <a href="${verifyUrl}" style="background: #667eea; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">Confirm Subscription</a>
    </p>
    <p style="color: #6b7280; font-size: 14px;">This link expires in 24 hours.</p>
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
    <p style="color: #9ca3af; font-size: 12px;">${verifyUrl}</p>
  </div>
</body>
</html>`.trim();

  return sendEmail(config, {
    to: recipientEmail,
    toName: recipientName || undefined,
    subject: 'Confirm your AI News Weekly subscription',
    htmlBody,
  });
}
