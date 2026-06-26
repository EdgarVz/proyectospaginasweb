import argparse
import asyncio
import sys
from leadfinder.config import settings
from leadfinder.database import Database
from leadfinder.scraper import Scraper
from leadfinder.analyzer import Analyzer


def main():
    parser = argparse.ArgumentParser(description="LeadFinder")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a scraping campaign")
    run_parser.add_argument("--campaign", required=True)
    run_parser.add_argument("--keyword", required=True, help="Comma-separated list of keywords")
    run_parser.add_argument("--location", required=True)
    run_parser.add_argument("--country", default="Venezuela")
    run_parser.add_argument("--radius", type=int, default=5000)
    run_parser.add_argument("--min-rating", type=float, default=None)
    run_parser.add_argument("--exclude-domain", action="append", dest="exclude_domains", default=[])
    run_parser.add_argument("--broad", action="store_true", help="Fetch all establishments (uses places_nearby)")
    run_parser.add_argument("--analyze", action="store_true")

    serve_parser = subparsers.add_parser("serve", help="Start web dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "run":
        asyncio.run(run_campaign(args))
    elif args.command == "serve":
        run_server(args)
    else:
        parser.print_help()


async def run_campaign(args):
    if not settings.google_places_api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in .env")
        sys.exit(1)
    db = Database(settings.database_path)
    await db.initialize()
    campaign_id = await db.create_campaign(
        name=args.campaign, keyword=args.keyword, location=args.location, country=args.country
    )
    print(f"Created campaign #{campaign_id}: {args.campaign}")
    scraper = Scraper(api_key=settings.google_places_api_key)
    businesses = await scraper.run(
        keyword=args.keyword, location=args.location, radius=args.radius,
        min_rating=args.min_rating, exclude_domains=args.exclude_domains or None,
        broad=args.broad,
    )
    print(f"Found {len(businesses)} businesses with websites")
    for b in businesses:
        bid = await db.create_business(campaign_id=campaign_id, **b)
        await db.create_audit(business_id=bid)
    print("Businesses saved to database")
    if args.analyze and businesses:
        print("Starting analysis...")
        analyzer = Analyzer()
        for i, b in enumerate(businesses, 1):
            print(f"  [{i}/{len(businesses)}] Analyzing {b['website']}...")
            cursor = await db._conn.execute(
                "SELECT id FROM audits WHERE business_id = (SELECT id FROM businesses WHERE website = ? AND campaign_id = ?)",
                (b["website"], campaign_id),
            )
            row = await cursor.fetchone()
            if not row:
                continue
            audit_id = row["id"]
            await db.update_audit_status(audit_id, "running")
            try:
                metrics = await analyzer.analyze(b["website"])
                for key, value in metrics.items():
                    score = value if isinstance(value, (int, float)) else 0
                    details = str(value) if key == "technologies" else None
                    await db.save_metric(
                        audit_id=audit_id, metric_name=key, score=score, details=details
                    )
                await db.update_audit_status(audit_id, "done")
                print(f"    Done — Lead Score: {metrics.get('lead_score', 'N/A')}")
            except Exception as e:
                await db.update_audit_status(audit_id, "error", error_message=str(e))
                print(f"    Error: {e}")
    await db.close()
    print("Done!")


def run_server(args):
    import uvicorn

    uvicorn.run("leadfinder.web.app:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()
