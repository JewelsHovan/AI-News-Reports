#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import markdown
except ImportError:
    markdown = None


def _read_markdown(input_path: Path | None) -> str:
    if input_path is None:
        return sys.stdin.read()
    return input_path.read_text(encoding="utf-8")


def _first_heading(markdown_text: str) -> str | None:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _infer_date_range_from_name(path: Path | None) -> tuple[str | None, str | None]:
    if path is None:
        return None, None
    match = re.search(r"ai-news_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})", path.name)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _render_html(markdown_text: str) -> tuple[str, str]:
    if markdown is None:
        raise RuntimeError(
            "python-markdown is required. Install with: pip install markdown"
        )

    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "attr_list",
        ],
        extension_configs={
            "toc": {
                "toc_depth": "2-3",
            }
        },
        output_format="html5",
    )
    body_html = md.convert(markdown_text)
    toc_html = md.toc or ""
    return body_html, toc_html


def main() -> int:
    parser = argparse.ArgumentParser(description="Render AI news report markdown to HTML.")
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

    input_path = Path(args.input).resolve() if args.input else None
    if input_path and not input_path.exists():
        sys.stderr.write(f"error: input file not found: {input_path}\n")
        return 1

    if args.output:
        output_path = Path(args.output).resolve()
    elif input_path:
        output_path = input_path.with_suffix(".html")
    else:
        sys.stderr.write("error: --output is required when reading from stdin\n")
        return 1

    markdown_text = _read_markdown(input_path)
    title = _first_heading(markdown_text) or "AI News Report"
    start_date, end_date = _infer_date_range_from_name(input_path)

    body_html, toc_html = _render_html(markdown_text)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_range = None
    if start_date and end_date:
        date_range = f"{start_date} → {end_date}"

    html = f"""<!doctype html>
<html lang=\"en\" data-theme=\"light\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f7f7f2;
      --bg-elev: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --accent: #2563eb;
      --accent-2: #0f766e;
      --border: #e5e7eb;
      --code-bg: #0b1020;
      --code-text: #e5e7eb;
      --shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    }}

    html[data-theme=\"dark\"] {{
      --bg: #0b0f16;
      --bg-elev: #111827;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #60a5fa;
      --accent-2: #34d399;
      --border: #1f2937;
      --code-bg: #0b1020;
      --code-text: #e5e7eb;
      --shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "SF Pro Text", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background: radial-gradient(circle at 20% 10%, rgba(59, 130, 246, 0.12), transparent 45%),
                  radial-gradient(circle at 90% 5%, rgba(16, 185, 129, 0.12), transparent 40%),
                  var(--bg);
      color: var(--text);
      line-height: 1.7;
    }}

    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 24px 60px;
    }}

    header.site-header {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
      padding: 20px 24px;
      background: var(--bg-elev);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }}

    .title-block h1 {{
      margin: 0;
      font-size: clamp(1.6rem, 2vw + 1rem, 2.4rem);
      letter-spacing: -0.02em;
    }}

    .title-block p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .toolbar {{
      display: flex;
      gap: 12px;
      align-items: center;
    }}

    .toggle-btn {{
      appearance: none;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 999px;
      font-size: 0.9rem;
      cursor: pointer;
      transition: all 0.2s ease;
    }}

    .toggle-btn:hover {{
      transform: translateY(-1px);
      border-color: var(--accent);
    }}

    .layout {{
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      gap: 28px;
      margin-top: 28px;
    }}

    nav.toc {{
      position: sticky;
      top: 24px;
      align-self: start;
      padding: 18px 18px 8px;
      background: var(--bg-elev);
      border: 1px solid var(--border);
      border-radius: 16px;
    }}

    nav.toc h2 {{
      margin: 0 0 12px;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}

    nav.toc ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 6px;
      font-size: 0.92rem;
    }}

    nav.toc a {{
      color: var(--text);
      text-decoration: none;
      padding: 6px 8px;
      border-radius: 8px;
      display: block;
    }}

    nav.toc a:hover {{
      background: rgba(37, 99, 235, 0.12);
      color: var(--accent);
    }}

    main.report {{
      background: var(--bg-elev);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 28px 32px;
      box-shadow: var(--shadow);
      min-width: 0;
    }}

    main.report h1, main.report h2, main.report h3, main.report h4 {{
      margin-top: 1.8em;
      margin-bottom: 0.5em;
      line-height: 1.3;
      letter-spacing: -0.01em;
    }}

    main.report h2 {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .collapse-toggle {{
      margin-left: auto;
      font-size: 0.8rem;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--muted);
      padding: 4px 10px;
      border-radius: 999px;
      cursor: pointer;
    }}

    .section {{
      border-top: 1px solid var(--border);
      padding-top: 16px;
    }}

    .section.collapsed .section-content {{
      display: none;
    }}

    main.report p {{
      margin: 0.8em 0;
    }}

    main.report a {{
      color: var(--accent);
      text-decoration: none;
      border-bottom: 1px solid rgba(37, 99, 235, 0.4);
      transition: all 0.2s ease;
    }}

    main.report a:hover {{
      color: var(--accent-2);
      border-bottom-color: rgba(15, 118, 110, 0.5);
    }}

    main.report blockquote {{
      border-left: 4px solid var(--accent);
      margin: 16px 0;
      padding: 8px 16px;
      background: rgba(37, 99, 235, 0.08);
      border-radius: 8px;
    }}

    main.report table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 0.95rem;
    }}

    main.report th, main.report td {{
      border: 1px solid var(--border);
      padding: 8px 10px;
      text-align: left;
    }}

    pre {{
      background: var(--code-bg);
      color: var(--code-text);
      padding: 16px;
      border-radius: 12px;
      overflow-x: auto;
      font-size: 0.9rem;
    }}

    code {{
      font-family: "SF Mono", "Cascadia Code", Menlo, monospace;
    }}

    .tok-keyword {{ color: #7dd3fc; font-weight: 600; }}
    .tok-string {{ color: #fca5a5; }}
    .tok-number {{ color: #fde68a; }}
    .tok-comment {{ color: #9ca3af; font-style: italic; }}

    footer.site-footer {{
      margin-top: 20px;
      text-align: center;
      color: var(--muted);
      font-size: 0.85rem;
    }}

    @media (max-width: 960px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}

      nav.toc {{
        position: static;
      }}
    }}

    @media print {{
      body {{
        background: white;
        color: black;
      }}
      header.site-header, nav.toc, .collapse-toggle {{
        display: none !important;
      }}
      main.report {{
        box-shadow: none;
        border: none;
        padding: 0;
      }}
      .section.collapsed .section-content {{
        display: block !important;
      }}
      a::after {{
        content: " (" attr(href) ")";
        font-size: 0.8em;
        color: #555;
      }}
    }}
  </style>
</head>
<body>
  <div class=\"page\">
    <header class=\"site-header\">
      <div class=\"title-block\">
        <h1>{title}</h1>
        <p>{date_range or ""}</p>
      </div>
      <div class=\"toolbar\">
        <button class=\"toggle-btn\" id=\"theme-toggle\" type=\"button\">Toggle theme</button>
      </div>
    </header>

    <div class=\"layout\">
      <nav class=\"toc\" aria-label=\"Table of contents\">
        <h2>Contents</h2>
        {toc_html or '<p class="toc-empty">No headings found.</p>'}
      </nav>

      <main class=\"report\" id=\"report\">
        {body_html}
      </main>
    </div>

    <footer class=\"site-footer\">
      Generated {now} UTC · Self-contained HTML
    </footer>
  </div>

  <script>
    (function () {{
      const root = document.documentElement;
      const stored = localStorage.getItem('theme');
      if (stored) {{
        root.setAttribute('data-theme', stored);
      }} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {{
        root.setAttribute('data-theme', 'dark');
      }}

      const toggle = document.getElementById('theme-toggle');
      if (toggle) {{
        toggle.addEventListener('click', () => {{
          const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
          root.setAttribute('data-theme', next);
          localStorage.setItem('theme', next);
        }});
      }}

      function escapeHtml(text) {{
        return text
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');
      }}

      function highlight(text) {{
        const regex = /\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*|#[^\\n]*|\"(?:\\\\.|[^\"\\\\])*\"|'(?:\\\\.|[^'\\\\])*'|`(?:\\\\.|[^`\\\\])*`|\\b\\d+(?:\\.\\d+)?\\b|\\b(class|def|function|return|if|else|for|while|try|catch|import|from|const|let|var|new|async|await|yield|True|False|None|null|true|false)\\b/g;
        let out = '';
        let lastIndex = 0;
        let match;
        while ((match = regex.exec(text)) !== null) {{
          out += escapeHtml(text.slice(lastIndex, match.index));
          const token = match[0];
          let cls = 'tok-keyword';
          if (token.startsWith('/*') || token.startsWith('//') || token.startsWith('#')) {{
            cls = 'tok-comment';
          }} else if (token.startsWith('"') || token.startsWith('\'') || token.startsWith('`')) {{
            cls = 'tok-string';
          }} else if (/^\\d/.test(token)) {{
            cls = 'tok-number';
          }}
          out += `<span class=\"${{cls}}\">${{escapeHtml(token)}}</span>`;
          lastIndex = regex.lastIndex;
        }}
        out += escapeHtml(text.slice(lastIndex));
        return out;
      }}

      document.querySelectorAll('pre code').forEach((block) => {{
        const raw = block.textContent || '';
        block.innerHTML = highlight(raw);
      }});

      function makeCollapsibleSections() {{
        const headings = Array.from(document.querySelectorAll('main.report h2'));
        headings.forEach((heading) => {{
          const section = document.createElement('section');
          section.className = 'section';
          const content = document.createElement('div');
          content.className = 'section-content';

          let sibling = heading.nextSibling;
          while (sibling && !(sibling.nodeType === 1 && sibling.tagName === 'H2')) {{
            const next = sibling.nextSibling;
            content.appendChild(sibling);
            sibling = next;
          }}

          const parent = heading.parentNode;
          parent.insertBefore(section, heading);
          section.appendChild(heading);
          section.appendChild(content);

          const toggleBtn = document.createElement('button');
          toggleBtn.className = 'collapse-toggle';
          toggleBtn.type = 'button';
          toggleBtn.setAttribute('aria-expanded', 'true');
          toggleBtn.textContent = 'Collapse';
          toggleBtn.addEventListener('click', () => {{
            const collapsed = section.classList.toggle('collapsed');
            toggleBtn.setAttribute('aria-expanded', String(!collapsed));
            toggleBtn.textContent = collapsed ? 'Expand' : 'Collapse';
          }});
          heading.appendChild(toggleBtn);
        }});
      }}

      makeCollapsibleSections();
    }})();
  </script>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    sys.stdout.write(str(output_path) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(1)
