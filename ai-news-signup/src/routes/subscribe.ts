import { Hono } from 'hono';
import { Env, SubscribeRequest, Subscriber, ApiResponse } from '../types';
import { validateTurnstile } from '../lib/turnstile';

export const subscribeRoute = new Hono<{ Bindings: Env }>();

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

subscribeRoute.post('/', async (c) => {
  try {
    let body: SubscribeRequest;
    try {
      body = await c.req.json();
    } catch {
      return c.json<ApiResponse>({ success: false, error: 'Invalid JSON body' }, 400);
    }

    const { email, name, turnstileToken } = body;

    if (!email || typeof email !== 'string') {
      return c.json<ApiResponse>({ success: false, error: 'Email is required' }, 400);
    }

    if (!turnstileToken || typeof turnstileToken !== 'string') {
      return c.json<ApiResponse>({ success: false, error: 'Turnstile token is required' }, 400);
    }

    const normalizedEmail = email.toLowerCase().trim();
    if (!EMAIL_REGEX.test(normalizedEmail)) {
      return c.json<ApiResponse>({ success: false, error: 'Invalid email format' }, 400);
    }

    const sanitizedName = name?.trim().slice(0, 100) || null;

    // Validate Turnstile
    const clientIp = c.req.header('CF-Connecting-IP');
    const turnstileResult = await validateTurnstile(c.env.TURNSTILE_SECRET_KEY, turnstileToken, clientIp);
    if (!turnstileResult.success) {
      return c.json<ApiResponse>({ success: false, error: turnstileResult.error || 'Captcha failed' }, 400);
    }

    // Check existing subscriber
    const existing = await c.env.DB.prepare(
      'SELECT id, email, verified, active FROM subscribers WHERE email = ?'
    ).bind(normalizedEmail).first<Subscriber>();

    if (existing) {
      if (existing.verified && existing.active) {
        return c.json<ApiResponse>({ success: true, message: 'You are already subscribed!' });
      }

      if (existing.verified && !existing.active) {
        await c.env.DB.prepare('UPDATE subscribers SET active = 1 WHERE id = ?').bind(existing.id).run();
        return c.json<ApiResponse>({ success: true, message: 'Welcome back! Subscription reactivated.' });
      }

      // Auto-verify unverified subscriber (Turnstile passed = trusted)
      await c.env.DB.prepare(
        'UPDATE subscribers SET verified = 1, verified_at = CURRENT_TIMESTAMP, active = 1, name = COALESCE(?, name) WHERE id = ?'
      ).bind(sanitizedName, existing.id).run();

      return c.json<ApiResponse>({ success: true, message: "You're subscribed! You'll receive the next newsletter." });
    }

    // New subscriber - auto-verified (Turnstile passed = trusted)
    await c.env.DB.prepare(
      'INSERT INTO subscribers (email, name, verified, verified_at, active) VALUES (?, ?, 1, CURRENT_TIMESTAMP, 1)'
    ).bind(normalizedEmail, sanitizedName).run();

    return c.json<ApiResponse>({ success: true, message: "You're subscribed! You'll receive the next newsletter." });
  } catch (error) {
    console.error('Subscribe error:', error);
    return c.json<ApiResponse>({ success: false, error: 'An unexpected error occurred.' }, 500);
  }
});
