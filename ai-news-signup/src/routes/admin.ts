import { Hono } from 'hono';
import { Env, ApiResponse, Subscriber } from '../types';
import { generateHmacToken } from '../lib/hmac';

export const adminRoute = new Hono<{ Bindings: Env }>();

interface SubscriberWithUnsubscribe {
  name: string | null;
  email: string;
  active: boolean;
  unsubscribeUrl: string;
}

adminRoute.get('/subscribers', async (c) => {
  const secret = c.req.query('secret');

  if (!secret || secret !== c.env.ADMIN_API_SECRET) {
    return c.json<ApiResponse>({ success: false, error: 'Unauthorized' }, 401);
  }

  try {
    const { results } = await c.env.DB.prepare(
      'SELECT name, email FROM subscribers WHERE verified = 1 AND active = 1 ORDER BY created_at ASC'
    ).all<Pick<Subscriber, 'name' | 'email'>>();

    const subscribers: SubscriberWithUnsubscribe[] = await Promise.all(
      (results || []).map(async (sub) => {
        const token = await generateHmacToken(c.env.HMAC_SECRET, sub.email);
        const unsubscribeUrl = `${c.env.WORKER_URL}/unsubscribe?email=${encodeURIComponent(sub.email)}&token=${token}`;

        return {
          name: sub.name,
          email: sub.email,
          active: true,
          unsubscribeUrl,
        };
      })
    );

    return c.json<ApiResponse<SubscriberWithUnsubscribe[]>>({ success: true, data: subscribers });
  } catch (error) {
    console.error('Admin subscribers error:', error);
    return c.json<ApiResponse>({ success: false, error: 'Failed to fetch subscribers' }, 500);
  }
});

adminRoute.get('/stats', async (c) => {
  const secret = c.req.query('secret');

  if (!secret || secret !== c.env.ADMIN_API_SECRET) {
    return c.json<ApiResponse>({ success: false, error: 'Unauthorized' }, 401);
  }

  try {
    const total = await c.env.DB.prepare('SELECT COUNT(*) as count FROM subscribers').first<{ count: number }>();
    const verified = await c.env.DB.prepare('SELECT COUNT(*) as count FROM subscribers WHERE verified = 1').first<{ count: number }>();
    const active = await c.env.DB.prepare('SELECT COUNT(*) as count FROM subscribers WHERE verified = 1 AND active = 1').first<{ count: number }>();

    return c.json<ApiResponse>({
      success: true,
      data: {
        total: total?.count || 0,
        verified: verified?.count || 0,
        active: active?.count || 0,
      },
    });
  } catch (error) {
    console.error('Admin stats error:', error);
    return c.json<ApiResponse>({ success: false, error: 'Failed to fetch stats' }, 500);
  }
});
