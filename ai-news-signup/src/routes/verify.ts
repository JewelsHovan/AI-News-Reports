import { Hono } from 'hono';
import { Env, Subscriber } from '../types';

export const verifyRoute = new Hono<{ Bindings: Env }>();

const successHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Subscription Confirmed</title>
  <style>
    body { font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f7f5f0; }
    .card { background: white; padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; border: 1px solid #e4e0d6; box-shadow: 0 10px 40px rgba(0,0,0,0.06); }
    .icon { width: 60px; height: 60px; background: #c2410c; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; color: white; font-size: 30px; }
    h1 { margin: 0 0 10px; color: #1b1a17; font-family: 'Iowan Old Style', Palatino, Georgia, serif; }
    p { color: #6b675f; } a { color: #c2410c; font-weight: 600; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">&#10003;</div>
    <h1>You're Subscribed!</h1>
    <p>Welcome to Julien's AI Brief. The next issue arrives Monday or Thursday morning.</p>
    <p><a href="https://julienhovan.com/AI-News-Reports/issue.html">Read the latest issue &rarr;</a></p>
  </div>
</body>
</html>`;

const errorHtml = (msg: string) => `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verification Failed</title>
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
    <h1>Verification Failed</h1>
    <p>${msg}</p>
  </div>
</body>
</html>`;

verifyRoute.get('/', async (c) => {
  const token = c.req.query('token');

  if (!token || token.length !== 32) {
    return c.html(errorHtml('Invalid or missing verification token.'), 400);
  }

  try {
    const subscriber = await c.env.DB.prepare(
      'SELECT id, verified FROM subscribers WHERE verification_token = ?'
    ).bind(token).first<Subscriber>();

    if (!subscriber) {
      return c.html(errorHtml('This link is invalid or has expired.'), 404);
    }

    if (subscriber.verified) {
      return c.html(successHtml);
    }

    await c.env.DB.prepare(
      'UPDATE subscribers SET verified = 1, verification_token = NULL, verified_at = unixepoch() WHERE id = ?'
    ).bind(subscriber.id).run();

    return c.html(successHtml);
  } catch (error) {
    console.error('Verification error:', error);
    return c.html(errorHtml('An error occurred. Please try again.'), 500);
  }
});
