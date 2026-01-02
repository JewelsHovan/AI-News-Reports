import { Hono } from 'hono';
import { Env, ApiResponse, ArchiveIndex, ReportMeta } from './types';

export const archiveRoute = new Hono<{ Bindings: Env }>();

const ARCHIVE_INDEX_KEY = 'archive-index';

/**
 * Verify admin authorization via Bearer token
 */
function isAuthorized(c: { req: { header: (name: string) => string | undefined }; env: Env }): boolean {
  const authHeader = c.req.header('Authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return false;
  }
  const token = authHeader.slice(7);
  return token === c.env.ADMIN_API_SECRET;
}

/**
 * Get the archive index from KV, or return empty index if not found
 */
async function getArchiveIndex(kv: KVNamespace): Promise<ArchiveIndex> {
  const data = await kv.get(ARCHIVE_INDEX_KEY, 'json');
  if (!data) {
    return { reports: [], updated_at: new Date().toISOString() };
  }
  return data as ArchiveIndex;
}

/**
 * Save the archive index to KV
 */
async function saveArchiveIndex(kv: KVNamespace, index: ArchiveIndex): Promise<void> {
  index.updated_at = new Date().toISOString();
  await kv.put(ARCHIVE_INDEX_KEY, JSON.stringify(index));
}

// GET /archive - Return the archive index (public)
archiveRoute.get('/', async (c) => {
  try {
    const index = await getArchiveIndex(c.env.ARCHIVE_KV);
    return c.json<ApiResponse<ArchiveIndex>>({
      success: true,
      data: index,
    });
  } catch (error) {
    console.error('Error fetching archive index:', error);
    return c.json<ApiResponse>({
      success: false,
      error: 'Failed to fetch archive index',
    }, 500);
  }
});

// GET /archive/:id - Return HTML report from R2 (public)
archiveRoute.get('/:id', async (c) => {
  const id = c.req.param('id');

  try {
    // First check if report exists in index
    const index = await getArchiveIndex(c.env.ARCHIVE_KV);
    const report = index.reports.find((r) => r.id === id);

    if (!report) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Report not found',
      }, 404);
    }

    // Fetch HTML from R2
    const object = await c.env.ARCHIVE_R2.get(report.r2_key);

    if (!object) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Report content not found in storage',
      }, 404);
    }

    const html = await object.text();

    return new Response(html, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (error) {
    console.error('Error fetching report:', error);
    return c.json<ApiResponse>({
      success: false,
      error: 'Failed to fetch report',
    }, 500);
  }
});

// POST /archive - Upload a new report (admin only)
archiveRoute.post('/', async (c) => {
  if (!isAuthorized(c)) {
    return c.json<ApiResponse>({
      success: false,
      error: 'Unauthorized',
    }, 401);
  }

  try {
    // Extract metadata from headers
    const reportId = c.req.header('X-Report-Id');
    const dateStart = c.req.header('X-Date-Start');
    const dateEnd = c.req.header('X-Date-End');
    const generatedAt = c.req.header('X-Generated-At');
    const title = c.req.header('X-Title');
    const summary = c.req.header('X-Summary');
    const days = c.req.header('X-Days');
    const totalItems = c.req.header('X-Total-Items');

    // Validate required headers
    if (!reportId || !dateStart || !dateEnd || !generatedAt || !title || !summary || !days || !totalItems) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Missing required headers: X-Report-Id, X-Date-Start, X-Date-End, X-Generated-At, X-Title, X-Summary, X-Days, X-Total-Items',
      }, 400);
    }

    // Get HTML body
    const html = await c.req.text();
    if (!html || html.trim().length === 0) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Request body must contain HTML content',
      }, 400);
    }

    // Construct R2 key
    const r2Key = `reports/${reportId}.html`;

    // Create report metadata
    const reportMeta: ReportMeta = {
      id: reportId,
      date_range_start: dateStart,
      date_range_end: dateEnd,
      generated_at: generatedAt,
      title,
      summary,
      r2_key: r2Key,
      days: parseInt(days, 10),
      total_items: parseInt(totalItems, 10),
    };

    // Upload HTML to R2
    await c.env.ARCHIVE_R2.put(r2Key, html, {
      httpMetadata: {
        contentType: 'text/html; charset=utf-8',
      },
    });

    // Update index
    const index = await getArchiveIndex(c.env.ARCHIVE_KV);

    // Check if report already exists (update) or is new (add)
    const existingIndex = index.reports.findIndex((r) => r.id === reportId);
    if (existingIndex >= 0) {
      index.reports[existingIndex] = reportMeta;
    } else {
      index.reports.push(reportMeta);
    }

    // Sort reports by date_range_end descending (newest first)
    index.reports.sort((a, b) => b.date_range_end.localeCompare(a.date_range_end));

    await saveArchiveIndex(c.env.ARCHIVE_KV, index);

    return c.json<ApiResponse<ReportMeta>>({
      success: true,
      message: existingIndex >= 0 ? 'Report updated' : 'Report uploaded',
      data: reportMeta,
    }, existingIndex >= 0 ? 200 : 201);
  } catch (error) {
    console.error('Error uploading report:', error);
    return c.json<ApiResponse>({
      success: false,
      error: 'Failed to upload report',
    }, 500);
  }
});

// PATCH /archive/:id - Update metadata only (admin only)
archiveRoute.patch('/:id', async (c) => {
  if (!isAuthorized(c)) {
    return c.json<ApiResponse>({
      success: false,
      error: 'Unauthorized',
    }, 401);
  }

  const id = c.req.param('id');

  try {
    const body = await c.req.json<{ title?: string; summary?: string }>();

    if (!body.title && !body.summary) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Request body must contain at least one of: title, summary',
      }, 400);
    }

    const index = await getArchiveIndex(c.env.ARCHIVE_KV);
    const reportIndex = index.reports.findIndex((r) => r.id === id);

    if (reportIndex < 0) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Report not found',
      }, 404);
    }

    // Update only provided fields
    if (body.title) {
      index.reports[reportIndex].title = body.title;
    }
    if (body.summary) {
      index.reports[reportIndex].summary = body.summary;
    }

    await saveArchiveIndex(c.env.ARCHIVE_KV, index);

    return c.json<ApiResponse<ReportMeta>>({
      success: true,
      message: 'Report metadata updated',
      data: index.reports[reportIndex],
    });
  } catch (error) {
    console.error('Error updating report metadata:', error);
    return c.json<ApiResponse>({
      success: false,
      error: 'Failed to update report metadata',
    }, 500);
  }
});

// DELETE /archive/:id - Remove report from R2 and index (admin only)
archiveRoute.delete('/:id', async (c) => {
  if (!isAuthorized(c)) {
    return c.json<ApiResponse>({
      success: false,
      error: 'Unauthorized',
    }, 401);
  }

  const id = c.req.param('id');

  try {
    const index = await getArchiveIndex(c.env.ARCHIVE_KV);
    const reportIndex = index.reports.findIndex((r) => r.id === id);

    if (reportIndex < 0) {
      return c.json<ApiResponse>({
        success: false,
        error: 'Report not found',
      }, 404);
    }

    const report = index.reports[reportIndex];

    // Delete from R2
    await c.env.ARCHIVE_R2.delete(report.r2_key);

    // Remove from index
    index.reports.splice(reportIndex, 1);
    await saveArchiveIndex(c.env.ARCHIVE_KV, index);

    return c.json<ApiResponse>({
      success: true,
      message: 'Report deleted',
    });
  } catch (error) {
    console.error('Error deleting report:', error);
    return c.json<ApiResponse>({
      success: false,
      error: 'Failed to delete report',
    }, 500);
  }
});
