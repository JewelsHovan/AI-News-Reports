import { Hono } from 'hono';
import { Env } from '../types';
import { validateHmacToken } from '../lib/hmac';

export const unsubscribeRoute = new Hono<{ Bindings: Env }>();

const successHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unsubscribed</title>
  <style>
    body { font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f7f5f0; }
    .card { background: white; padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; border: 1px solid #e4e0d6; box-shadow: 0 10px 40px rgba(0,0,0,0.06); }
    .icon { width: 60px; height: 60px; background: #6b7280; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; }
    h1 { margin: 0 0 10px; color: #1b1a17; font-family: 'Iowan Old Style', Palatino, Georgia, serif; }
    p { color: #6b675f; } a { color: #c2410c; font-weight: 600; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">&#128075;</div>
    <h1>Unsubscribed</h1>
    <p>You've been removed from Julien's AI Brief. Sorry to see you go!</p>
    <p><a href="https://julienhovan.com/AI-News-Reports/">Changed your mind? Subscribe again</a></p>
  </div>
</body>
</html>`;

const errorHtml = (msg: string) => `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unsubscribe Error</title>
  <style>
    body { font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f7f5f0; }
    .card { background: white; padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; border: 1px solid #e4e0d6; box-shadow: 0 10px 40px rgba(0,0,0,0.06); }
    .icon { width: 60px; height: 60px; background: #ef4444; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; color: white; font-size: 30px; }
    h1 { margin: 0 0 10px; color: #1b1a17; font-family: 'Iowan Old Style', Palatino, Georgia, serif; }
    p { color: #6b675f; } a { color: #c2410c; font-weight: 600; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">&#10005;</div>
    <h1>Error</h1>
    <p>${msg}</p>
  </div>
</body>
</html>`;

unsubscribeRoute.get('/', async (c) => {
  const email = c.req.query('email');
  const token = c.req.query('token');

  if (!email || !token) {
    return c.html(errorHtml('Invalid unsubscribe link.'), 400);
  }

  const normalizedEmail = email.toLowerCase().trim();

  try {
    const isValid = await validateHmacToken(c.env.HMAC_SECRET, normalizedEmail, token);
    if (!isValid) {
      return c.html(errorHtml('Invalid unsubscribe link.'), 403);
    }

    await c.env.DB.prepare(
      'UPDATE subscribers SET active = 0 WHERE email = ?'
    ).bind(normalizedEmail).run();

    return c.html(successHtml);
  } catch (error) {
    console.error('Unsubscribe error:', error);
    return c.html(errorHtml('An error occurred. Please try again.'), 500);
  }
});
