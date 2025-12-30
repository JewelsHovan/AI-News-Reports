#!/usr/bin/env python3
"""
Render AI news report markdown to email-safe HTML.

This module generates HTML that is compatible with email clients including
Outlook Desktop (which uses Microsoft Word's ~2007 rendering engine).

Key constraints for email HTML:
- Table-based layout (no CSS Grid or Flexbox)
- Inline styles only (no CSS variables, limited <style> support)
- Fixed 600px content width (standard email width)
- Safe fonts only (Arial, Helvetica, sans-serif)
- No JavaScript (stripped by email clients)
- No interactivity (no theme toggle, collapsible sections)
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import markdown
except ImportError:
    markdown = None


# =============================================================================
# Style Configuration
# =============================================================================

# Color palette (flat values, no CSS variables)
COLORS = {
    "bg_outer": "#f5f5f5",
    "bg_content": "#ffffff",
    "bg_header": "#1e293b",
    "bg_footer": "#f8fafc",
    "bg_code": "#1e293b",
    "bg_code_inline": "#f1f5f9",
    "bg_blockquote": "#f1f5f9",
    "bg_table_header": "#f1f5f9",
    "text_primary": "#374151",
    "text_heading": "#1e293b",
    "text_heading_secondary": "#334155",
    "text_heading_tertiary": "#475569",
    "text_muted": "#64748b",
    "text_header": "#ffffff",
    "text_header_sub": "#94a3b8",
    "text_code": "#e2e8f0",
    "text_code_inline": "#be185d",
    "accent": "#2563eb",
    "border": "#e2e8f0",
}

# Inline styles for HTML elements
INLINE_STYLES = {
    "h1": (
        f"font-size:28px; color:{COLORS['text_heading']}; margin:32px 0 12px; "
        f"font-weight:700; font-family:Arial,Helvetica,sans-serif;"
    ),
    "h2": (
        f"font-size:22px; color:{COLORS['text_heading_secondary']}; margin:28px 0 12px; "
        f"font-weight:600; font-family:Arial,Helvetica,sans-serif; "
        f"border-bottom:2px solid {COLORS['border']}; padding-bottom:10px;"
    ),
    "h3": (
        f"font-size:18px; color:{COLORS['text_heading_tertiary']}; margin:24px 0 10px; "
        f"font-weight:600; font-family:Arial,Helvetica,sans-serif;"
    ),
    "h4": (
        f"font-size:16px; color:{COLORS['text_heading_tertiary']}; margin:20px 0 8px; "
        f"font-weight:600; font-family:Arial,Helvetica,sans-serif;"
    ),
    "h5": (
        f"font-size:15px; color:{COLORS['text_heading_tertiary']}; margin:18px 0 8px; "
        f"font-weight:600; font-family:Arial,Helvetica,sans-serif;"
    ),
    "h6": (
        f"font-size:14px; color:{COLORS['text_heading_tertiary']}; margin:16px 0 6px; "
        f"font-weight:600; font-family:Arial,Helvetica,sans-serif;"
    ),
    "p": (
        f"font-size:15px; color:{COLORS['text_primary']}; line-height:1.7; "
        f"margin:0 0 14px; font-family:Arial,Helvetica,sans-serif;"
    ),
    "a": f"color:{COLORS['accent']}; text-decoration:underline;",
    "ul": "margin:0 0 16px; padding-left:24px;",
    "ol": "margin:0 0 16px; padding-left:24px;",
    "li": (
        f"font-size:15px; color:{COLORS['text_primary']}; line-height:1.7; "
        f"margin-bottom:8px; font-family:Arial,Helvetica,sans-serif;"
    ),
    "blockquote": (
        f"margin:16px 0; padding:14px 18px; background-color:{COLORS['bg_blockquote']}; "
        f"border-left:4px solid {COLORS['accent']}; border-radius:0 6px 6px 0;"
    ),
    "table": "width:100%; border-collapse:collapse; margin:16px 0;",
    "th": (
        f"padding:12px 14px; background-color:{COLORS['bg_table_header']}; "
        f"border:1px solid {COLORS['border']}; text-align:left; font-weight:600; "
        f"font-size:14px; color:{COLORS['text_primary']};"
    ),
    "td": (
        f"padding:12px 14px; border:1px solid {COLORS['border']}; "
        f"font-size:14px; color:{COLORS['text_primary']};"
    ),
    "code": (
        f"font-family:'Courier New',Courier,monospace; background-color:{COLORS['bg_code_inline']}; "
        f"padding:2px 6px; font-size:13px; border-radius:4px; color:{COLORS['text_code_inline']};"
    ),
    "pre": (
        f"background-color:{COLORS['bg_code']}; color:{COLORS['text_code']}; "
        f"padding:16px 20px; font-family:'Courier New',Courier,monospace; "
        f"font-size:13px; line-height:1.5; overflow-x:auto; border-radius:6px; margin:16px 0;"
    ),
    "hr": f"border:none; border-top:2px solid {COLORS['border']}; margin:28px 0;",
    "strong": f"font-weight:700; color:{COLORS['text_heading']};",
    "b": f"font-weight:700; color:{COLORS['text_heading']};",
    "em": "font-style:italic;",
    "i": "font-style:italic;",
}


# =============================================================================
# Unsubscribe Footer Template
# =============================================================================

# The {UNSUBSCRIBE_LINK} placeholder will be replaced by send_newsletter.py
# with a personalized unsubscribe URL for each recipient.
UNSUBSCRIBE_FOOTER = '''
              <!-- Unsubscribe Footer -->
              <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 12px; color: #666666; font-family: Arial, Helvetica, sans-serif;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 12px;">You received this because you subscribed to AI News.</p>
                <p style="margin: 0; color: #666666; font-size: 12px;"><a href="{UNSUBSCRIBE_LINK}" style="color: #666666; text-decoration: underline;">Unsubscribe</a></p>
              </div>
'''


# =============================================================================
# Helper Functions
# =============================================================================


def _read_markdown(input_path: Path | None) -> str:
    """Read markdown content from file or stdin."""
    if input_path is None:
        return sys.stdin.read()
    return input_path.read_text(encoding="utf-8")


def _first_heading(markdown_text: str) -> str | None:
    """Extract the first H1 heading from markdown text."""
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _infer_date_range_from_name(path: Path | None) -> tuple[str | None, str | None]:
    """Extract date range from filename pattern ai-news_YYYY-MM-DD_to_YYYY-MM-DD."""
    if path is None:
        return None, None
    match = re.search(r"ai-news_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})", path.name)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _apply_inline_styles(html: str) -> str:
    """
    Inject inline styles into HTML elements for email client compatibility.

    This function post-processes markdown-generated HTML to add inline styles
    to each element, ensuring compatibility with email clients that strip
    <style> blocks (like Outlook).

    Args:
        html: The HTML content generated by markdown conversion

    Returns:
        HTML with inline styles injected into each element
    """

    def inject_style(match: re.Match) -> str:
        """Inject style attribute into an HTML tag."""
        tag = match.group(1).lower()
        existing_attrs = match.group(2) or ""
        style = INLINE_STYLES.get(tag, "")

        if not style:
            return match.group(0)

        # Check if there's already a style attribute
        if 'style="' in existing_attrs.lower():
            # Merge our style with existing style (our style takes precedence)
            existing_attrs = re.sub(
                r'style="([^"]*)"',
                f'style="{style} \\1"',
                existing_attrs,
                flags=re.IGNORECASE
            )
            return f"<{tag}{existing_attrs}>"

        # Add new style attribute
        if existing_attrs and not existing_attrs.startswith(" "):
            existing_attrs = " " + existing_attrs
        return f'<{tag} style="{style}"{existing_attrs}>'

    # Match opening tags for elements we want to style
    # This pattern captures: <tagname optional-attributes>
    pattern = r"<(h[1-6]|p|a|ul|ol|li|blockquote|table|th|td|code|pre|hr|strong|b|em|i)(\s[^>]*)?\s*/?>"

    return re.sub(pattern, inject_style, html, flags=re.IGNORECASE)


def _render_markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown to HTML using python-markdown.

    Uses a minimal set of extensions for email-safe output:
    - fenced_code: For code blocks
    - tables: For markdown tables
    - attr_list: For adding custom attributes (rarely used in reports)

    Note: TOC extension is NOT used since we're removing the sidebar navigation.

    Args:
        markdown_text: Raw markdown content

    Returns:
        HTML body content (without wrapper)
    """
    if markdown is None:
        raise RuntimeError(
            "python-markdown is required. Install with: pip install markdown"
        )

    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "attr_list",
        ],
        output_format="html5",
    )
    return md.convert(markdown_text)


def _escape_html(text: str) -> str:
    """Escape special HTML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _strip_first_h1(html: str) -> str:
    """
    Remove the first H1 tag from HTML since title is already in header.

    The email template displays the title in a styled header row, so having
    the H1 repeated in the body content is redundant and wastes above-the-fold
    space in email clients.

    Args:
        html: HTML body content from markdown conversion

    Returns:
        HTML with the first H1 element removed
    """
    return re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html, count=1, flags=re.IGNORECASE | re.DOTALL)


def _extract_preheader(html: str, max_length: int = 150) -> str:
    """
    Extract first paragraph text for email preheader.

    The preheader appears in inbox previews next to the subject line and
    improves open rates by giving recipients a preview of the content.

    Args:
        html: HTML body content to extract preview text from
        max_length: Maximum length of preheader text (default 150 chars)

    Returns:
        Plain text suitable for preheader, or empty string if no content found
    """
    # Try to find Executive Summary content or first paragraph
    match = re.search(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
    if match:
        # Strip HTML tags from the content
        text = re.sub(r'<[^>]+>', '', match.group(1))
        text = text.strip()
        if len(text) > max_length:
            text = text[:max_length].rsplit(' ', 1)[0] + '...'
        return text
    return ''


def _build_email_template(
    title: str,
    date_range: str | None,
    body_html: str,
    timestamp: str,
    preheader: str = "",
) -> str:
    """
    Build the complete email-safe HTML document.

    Structure:
    - Outer table: Full-width wrapper with background color
    - Inner table: 600px centered content container
    - Header row: Title and date range
    - Body row: Converted markdown content
    - Footer row: Generation timestamp

    Args:
        title: Report title (from H1 heading)
        date_range: Optional date range string (e.g., "2025-01-01 - 2025-01-07")
        body_html: Styled HTML body content
        timestamp: ISO timestamp of generation
        preheader: Preview text shown in inbox next to subject line

    Returns:
        Complete HTML document as string
    """
    # Build date range row if provided
    date_row = ""
    if date_range:
        date_row = f'''
              <p style="margin:10px 0 0; color:{COLORS['text_header_sub']}; font-size:14px; font-family:Arial,Helvetica,sans-serif;">
                {_escape_html(date_range)}
              </p>'''

    # Build preheader div if we have preheader text
    preheader_div = ""
    if preheader:
        preheader_div = f'''
  <!--[if !mso]><!-->
  <div style="display:none;font-size:1px;color:{COLORS['bg_outer']};line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;mso-hide:all;">
    {_escape_html(preheader)}
  </div>
  <!--<![endif]-->'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <title>{_escape_html(title)}</title>
  <!--[if mso]>
  <style type="text/css">
    table {{ border-collapse: collapse; }}
    td {{ font-family: Arial, sans-serif; }}
    .body-content table {{ width: 100% !important; }}
  </style>
  <noscript>
  <xml>
    <o:OfficeDocumentSettings>
      <o:PixelsPerInch>96</o:PixelsPerInch>
    </o:OfficeDocumentSettings>
  </xml>
  </noscript>
  <![endif]-->
  <style type="text/css">
    /* Print styles - these are only used when printing, safe to keep in style block */
    @media print {{
      body {{
        background: white !important;
      }}
      .email-wrapper {{
        background: white !important;
      }}
      .content-container {{
        box-shadow: none !important;
      }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background-color:{COLORS['bg_outer']}; font-family:Arial,Helvetica,sans-serif; -webkit-font-smoothing:antialiased; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%;">{preheader_div}

  <!-- Outer wrapper table -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="email-wrapper" style="background-color:{COLORS['bg_outer']};">
    <tr>
      <td align="center" style="padding:24px 16px;">

        <!-- Main content container - 600px max width -->
        <!--[if mso]>
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" align="center">
        <tr>
        <td>
        <![endif]-->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="content-container" style="max-width:600px; background-color:{COLORS['bg_content']}; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="padding:28px 32px; background-color:{COLORS['bg_header']}; border-radius:8px 8px 0 0;">
              <h1 style="margin:0; color:{COLORS['text_header']}; font-size:26px; font-weight:700; font-family:Arial,Helvetica,sans-serif; line-height:1.3;">
                {_escape_html(title)}
              </h1>{date_row}
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td class="body-content" style="padding:28px 32px;">
              {body_html}
{UNSUBSCRIBE_FOOTER}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px; background-color:{COLORS['bg_footer']}; border-radius:0 0 8px 8px; text-align:center; border-top:1px solid {COLORS['border']};">
              <p style="margin:0; color:{COLORS['text_muted']}; font-size:12px; font-family:Arial,Helvetica,sans-serif;">
                Generated {timestamp} &middot; AI News Aggregator
              </p>
            </td>
          </tr>

        </table>
        <!--[if mso]>
        </td>
        </tr>
        </table>
        <![endif]-->

      </td>
    </tr>
  </table>

</body>
</html>'''


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """
    Main entry point for the HTML renderer.

    Accepts markdown input from file or stdin, converts to email-safe HTML,
    and writes to output file.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Render AI news report markdown to email-safe HTML."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to markdown report (defaults to stdin if omitted)",
    )
    parser.add_argument(
        "--output",
        help="Output HTML path (defaults to input path with .html)",
    )
    args = parser.parse_args()

    # Resolve input path
    input_path = Path(args.input).resolve() if args.input else None
    if input_path and not input_path.exists():
        sys.stderr.write(f"error: input file not found: {input_path}\n")
        return 1

    # Resolve output path
    if args.output:
        output_path = Path(args.output).resolve()
    elif input_path:
        output_path = input_path.with_suffix(".html")
    else:
        sys.stderr.write("error: --output is required when reading from stdin\n")
        return 1

    # Read and parse markdown
    markdown_text = _read_markdown(input_path)
    title = _first_heading(markdown_text) or "AI News Report"
    start_date, end_date = _infer_date_range_from_name(input_path)

    # Convert markdown to HTML
    body_html = _render_markdown_to_html(markdown_text)

    # Extract preheader text BEFORE stripping the H1 and applying styles
    # This ensures we get clean text from the first paragraph
    preheader = _extract_preheader(body_html)

    # Remove duplicate H1 since title is shown in header
    body_html = _strip_first_h1(body_html)

    # Apply inline styles for email compatibility
    body_html = _apply_inline_styles(body_html)

    # Build metadata
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_range = None
    if start_date and end_date:
        date_range = f"{start_date} \u2192 {end_date}"

    # Build complete HTML document
    html = _build_email_template(
        title=title,
        date_range=date_range,
        body_html=body_html,
        timestamp=now,
        preheader=preheader,
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    # Print output path to stdout (for scripting)
    sys.stdout.write(str(output_path) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(1)
