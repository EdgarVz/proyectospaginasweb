import csv
import io
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
import os

from leadfinder.analyzer import Analyzer
from leadfinder.config import settings
from leadfinder.database import Database
from leadfinder.scraper import Scraper

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True, cache_size=0)
templates = Jinja2Templates(env=env)
db: Database = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = Database(settings.database_path)
    await db.initialize()
    yield
    await db.close()


app = FastAPI(title="LeadFinder", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    summary = await db.get_summary()
    return templates.TemplateResponse(request, "dashboard.html", {"summary": summary})


@app.get("/leads", response_class=HTMLResponse)
async def leads_list(
    request: Request,
    country: str = None,
    category: str = None,
    min_score: float = None,
    status: str = None,
):
    businesses = await db.get_businesses(country=country, category=category, status=status)

    enriched = []
    for b in businesses:
        lead_score = None
        if b.get("audit_id") and b.get("audit_status") == "done":
            metrics = await db.get_metrics(b["audit_id"])
            for m in metrics:
                if m["metric_name"] == "lead_score":
                    lead_score = m["score"]
                    break
        enriched.append({**b, "lead_score": lead_score})

    if min_score is not None:
        enriched = [b for b in enriched if b["lead_score"] is not None and b["lead_score"] >= min_score]

    enriched.sort(key=lambda b: (b["lead_score"] is None, -(b["lead_score"] or 0)))

    return templates.TemplateResponse(request, "leads.html", {"leads": enriched})


@app.get("/leads/{lead_id}", response_class=HTMLResponse)
async def lead_detail(request: Request, lead_id: int):
    business = await db.get_business(lead_id)
    if not business:
        return HTMLResponse("Not found", status_code=404)

    cursor = await db._conn.execute("SELECT * FROM audits WHERE business_id = ?", (lead_id,))
    row = await cursor.fetchone()
    audit = dict(row) if row else None

    metrics = []
    if audit:
        metrics = await db.get_metrics(audit["id"])

    return templates.TemplateResponse(
        request, "lead_detail.html",
        {"business": business, "audit": audit, "metrics": metrics},
    )


@app.post("/leads/bulk-delete")
async def bulk_delete(ids: list[int] = Form(...)):
    await db.delete_businesses(ids)
    return HTMLResponse("")


@app.get("/leads/export")
async def export_leads():
    businesses = await db.get_businesses()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "website", "phone", "address", "rating", "category", "city", "country"])
    for b in businesses:
        writer.writerow([
            b["id"], b["name"], b["website"], b["phone"],
            b["address"], b["rating"], b["category"], b["city"], b["country"],
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns_list(request: Request):
    campaigns = await db.get_campaigns()
    return templates.TemplateResponse(request, "campaigns.html", {"campaigns": campaigns})


@app.post("/campaigns/new")
async def create_campaign(
    name: str = Form(...),
    keyword: str = Form(...),
    location: str = Form(...),
    country: str = Form("Venezuela"),
):
    if not settings.google_places_api_key:
        return HTMLResponse("Google Places API key not configured", status_code=400)

    campaign_id = await db.create_campaign(name, keyword, location, country)

    scraper = Scraper(settings.google_places_api_key)
    results = await scraper.run(keyword, location)

    for r in results:
        business_id = await db.create_business(
            campaign_id=campaign_id,
            name=r["name"],
            website=r["website"],
            phone=r.get("phone"),
            address=r.get("address"),
            rating=r.get("rating"),
            category=r.get("category"),
            city=r.get("city"),
            country=r.get("country", country),
            place_id=r.get("place_id"),
        )
        await db.create_audit(business_id)

    return HTMLResponse("")


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int):
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        return HTMLResponse("Not found", status_code=404)

    businesses = await db.get_businesses(campaign_id=campaign_id)
    return templates.TemplateResponse(
        request, "campaign_detail.html",
        {"campaign": campaign, "businesses": businesses},
    )


@app.post("/campaigns/{campaign_id}/analyze")
async def analyze_campaign(campaign_id: int):
    businesses = await db.get_businesses(campaign_id=campaign_id, status="pending")
    analyzer = Analyzer()

    for b in businesses:
        try:
            metrics = await analyzer.analyze(b["website"])
            await db.update_audit_status(b["audit_id"], "done")
            for name, score in metrics.items():
                if isinstance(score, (int, float)):
                    await db.save_metric(b["audit_id"], name, float(score))
                elif isinstance(score, list):
                    await db.save_metric(b["audit_id"], name, 0, json.dumps(score))
        except Exception as e:
            await db.update_audit_status(b["audit_id"], "error", str(e))

    return HTMLResponse("")
