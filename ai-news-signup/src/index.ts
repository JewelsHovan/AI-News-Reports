import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { Env } from './types';
import { subscribeRoute } from './routes/subscribe';
import { verifyRoute } from './routes/verify';
import { unsubscribeRoute } from './routes/unsubscribe';
import { adminRoute } from './routes/admin';
import { archiveRoute } from './archive';

const app = new Hono<{ Bindings: Env }>();

// CORS - allow requests from GitHub Pages and localhost
app.use('*', cors({
  origin: ['https://julienhovan.com', 'https://jewelshovan.github.io', 'https://julienh15.github.io', 'http://localhost:3000', 'http://localhost:8080'],
  allowMethods: ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization', 'X-Report-Id', 'X-Date-Start', 'X-Date-End', 'X-Generated-At', 'X-Title', 'X-Summary', 'X-Days', 'X-Total-Items'],
  maxAge: 86400,
}));

// Health check
app.get('/', (c) => c.json({ status: 'ok', service: 'ai-news-signup' }));

// Mount routes
app.route('/subscribe', subscribeRoute);
app.route('/verify', verifyRoute);
app.route('/unsubscribe', unsubscribeRoute);
app.route('/api', adminRoute);
app.route('/archive', archiveRoute);

// 404 handler
app.notFound((c) => c.json({ success: false, error: 'Not found' }, 404));

// Error handler
app.onError((err, c) => {
  console.error('Unhandled error:', err);
  return c.json({ success: false, error: 'Internal server error' }, 500);
});

export default app;
