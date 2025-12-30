import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { Env } from './types';
import { subscribeRoute } from './routes/subscribe';
import { verifyRoute } from './routes/verify';
import { unsubscribeRoute } from './routes/unsubscribe';
import { adminRoute } from './routes/admin';

const app = new Hono<{ Bindings: Env }>();

// CORS - allow requests from GitHub Pages and localhost
app.use('*', cors({
  origin: ['https://julienhovan.com', 'https://jewelshovan.github.io', 'http://localhost:3000', 'http://localhost:8080'],
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type'],
  maxAge: 86400,
}));

// Health check
app.get('/', (c) => c.json({ status: 'ok', service: 'ai-news-signup' }));

// Mount routes
app.route('/subscribe', subscribeRoute);
app.route('/verify', verifyRoute);
app.route('/unsubscribe', unsubscribeRoute);
app.route('/api', adminRoute);

// 404 handler
app.notFound((c) => c.json({ success: false, error: 'Not found' }, 404));

// Error handler
app.onError((err, c) => {
  console.error('Unhandled error:', err);
  return c.json({ success: false, error: 'Internal server error' }, 500);
});

export default app;
