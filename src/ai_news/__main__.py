"""AI News Pipeline CLI entry point."""

import argparse
import asyncio
import logging
import sys


def main():
    parser = argparse.ArgumentParser(
        description="AI News Pipeline - Aggregate and analyze AI news"
    )
    parser.add_argument(
        "--days", type=int, default=2, help="Days to look back (default: 2)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Skip upload and newsletter"
    )
    parser.add_argument(
        "--skip-newsletter", action="store_true", help="Skip sending newsletter"
    )
    parser.add_argument(
        "--skip-upload", action="store_true", help="Skip Cloudflare upload"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    from ai_news.pipeline import run_pipeline

    result = asyncio.run(
        run_pipeline(
            days=args.days,
            dry_run=args.dry_run,
            skip_newsletter=args.skip_newsletter,
            skip_upload=args.skip_upload,
        )
    )

    if result.success:
        print(f"Report: {result.report_path}")
        if result.html_path:
            print(f"HTML: {result.html_path}")
        if result.upload_url:
            print(f"Archive: {result.upload_url}")
        if result.newsletter_sent:
            print(f"Newsletter: sent to {result.newsletter_sent} subscribers")
        if result.errors:
            print(f"Warnings: {len(result.errors)}")
            for err in result.errors:
                print(f"  - {err}")
    else:
        print("Pipeline FAILED", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
