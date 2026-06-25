# LeadFinder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local tool that scrapes Google Places for businesses with websites, runs Lighthouse + HTML analysis, scores them by improvement need, and shows results in a FastAPI + HTMX dashboard.

**Architecture:** Python monorepo with 4 pipeline stages (scraper → analyzer → scoring → dashboard). SQLite for persistence, FastAPI for web serving, HTMX + Alpine.js for interactive UI without a heavy frontend framework.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, HTMX, Alpine.js, Tailwind CSS, googlemaps, beautifulsoup4, Lighthouse CLI

---

## File Structure

```
leadfinder/
├── __init__.py
├── __main__.py              # CLI: python -m leadfinder run ...
├── config.py                # Load .env vars
├── database.py              # SQLite schema + CRUD operations
├── models.py                # Pydantic models
├── lead_score.py            # Scoring formula
├── scraper.py               # Google Places API client
├── analyzer.py              # Lighthouse + HTML inspector
├── web/
│   ├── __init__.py
│   ├── app.py               # FastAPI app + route handlers
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── leads.html
│   │   ├── lead_detail.html
│   │   ├── campaigns.html
│   │   └── campaign_detail.html
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures
│   ├── test_lead_score.py
│   ├── test_scraper.py
│   ├── test_analyzer.py
│   └── test_database.py
├── requirements.txt
└── .env.example
```

---

### Task 1: Project skeleton, dependencies, config

**Files:**
- Create: `leadfinder/requirements.txt`
- Create: `leadfinder/.env.example`
- Create: `leadfinder/__init__.py`
- Create: `leadfinder/config.py`
- Create: `leadfinder/tests/__init__.py`
- Create: `leadfinder/tests/conftest.py`

- [ ] **Step 1: Write requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
aiosqlite>=0.20.0
httpx>=0.28.0
beautifulsoup4>=4.12.0
googlemaps>=4.10.0
python-dotenv>=1.0.0
pydantic>=2.0.0
jinja2>=3.1.0
python-multipart>=0.0.12
pytest>=8.0.0
pytest-asyncio>=0.24.0
pytest-httpx>=0.35.0
```

- [ ] **Step 2: Write .env.example**

```
GOOGLE_PLACES_API_KEY=your_api_key_here
DATABASE_PATH=leadfinder.db
```

- [ ] **Step 3: Write leadfinder/__init__.py**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Write leadfinder/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_places_api_key: str = ""
    database_path: str = "leadfinder.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 5: Write leadfinder/tests/__init__.py** (empty)

```python
```

- [ ] **Step 6: Write leadfinder/tests/conftest.py**

```python
import pytest


@pytest.fixture
def sample_business():
    return {
        "name": "Test Restaurant",
        "website": "https://test-restaurant.com",
        "phone": "+58 212 555 1234",
        "address": "Av. Principal, Caracas",
        "rating": 4.2,
        "category": "restaurante",
        "city": "Caracas",
        "country": "Venezuela",
        "place_id": "abc123",
    }
```

- [ ] **Step 7: Create directory and verify structure**

```bash
New-Item -ItemType Directory -Path "leadfinder/tests" -Force; New-Item -ItemType Directory -Path "leadfinder/web/templates" -Force
```

- [ ] **Step 8: Commit**

```bash
git add -A; git commit -m "chore: scaffold project skeleton with config"
```

---

### Task 2: Database module (SQLite schema + CRUD)

**Files:**
- Create: `leadfinder/database.py`
- Create: `leadfinder/tests/test_database.py`

- [ ] **Step 1: Write the failing test**


```python
import pytest
import pytest_asyncio
from leadfinder.database import Database


@pytest_asyncio.fixture
async def db():
    d = Database(":memory:")
    await d.initialize()
    yield d
    await d.close()


@pytest.mark.asyncio
async def test_create_and_get_campaign(db):
    cid = await db.create_campaign(
        name="Test Campaign",
        keyword="restaurantes",
        location="Caracas, Venezuela",
        country="Venezuela",
    )
    assert cid is not None
    campaign = await db.get_campaign(cid)
    assert campaign["name"] == "Test Campaign"
    assert campaign["keyword"] == "restaurantes"


@pytest.mark.asyncio
async def test_create_and_get_business(db, sample_business):
    cid = await db.create_campaign(name="C", keyword="k", location="L", country="V")
    bid = await db.create_business(campaign_id=cid, **sample_business)
    assert bid is not None
    business = await db.get_business(bid)
    assert business["name"] == "Test Restaurant"
    assert business["website"] == "https://test-restaurant.com"


@pytest.mark.asyncio
async def test_get_businesses_by_campaign(db, sample_business):
    cid = await db.create_campaign(name="C", keyword="k", location="L", country="V")
    await db.create_business(campaign_id=cid, **sample_business)
    businesses = await db.get_businesses(campaign_id=cid)
    assert len(businesses) == 1


@pytest.mark.asyncio
async def test_create_audit_and_metrics(db, sample_business):
    cid = await db.create_campaign(name="C", keyword="k", location="L", country="V")
    bid = await db.create_business(campaign_id=cid, **sample_business)
    aid = await db.create_audit(business_id=bid)
    assert aid is not None
    await db.save_metric(audit_id=aid, metric_name="performance_score", score=45.0)
    metrics = await db.get_metrics(audit_id=aid)
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "performance_score"
    assert metrics[0]["score"] == 45.0
```

Run: `pytest leadfinder/tests/test_database.py -v`
Expected: FAIL (module not found)

- [ ] **Step 2: Write minimal database.py**

```python
import aiosqlite
from typing import Optional


class Database:
    def __init__(self, path: str):
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._migrate()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def _migrate(self):
        sql = """
        CREATE TABLE IF NOT EXISTS campaigns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            keyword     TEXT NOT NULL,
            location    TEXT NOT NULL,
            country     TEXT NOT NULL DEFAULT 'Venezuela',
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS businesses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            name        TEXT NOT NULL,
            website     TEXT NOT NULL,
            phone       TEXT,
            address     TEXT,
            rating      REAL,
            category    TEXT,
            city        TEXT,
            country     TEXT,
            place_id    TEXT UNIQUE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id     INTEGER NOT NULL UNIQUE REFERENCES businesses(id),
            status          TEXT NOT NULL DEFAULT 'pending',
            lighthouse_json TEXT,
            error_message   TEXT,
            analyzed_at     TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id    INTEGER NOT NULL REFERENCES audits(id),
            metric_name TEXT NOT NULL,
            score       REAL NOT NULL,
            details     TEXT,
            UNIQUE(audit_id, metric_name)
        );
        """
        await self._conn.executescript(sql)
        await self._conn.commit()

    async def create_campaign(self, name: str, keyword: str, location: str, country: str) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO campaigns (name, keyword, location, country) VALUES (?, ?, ?, ?)",
            (name, keyword, location, country),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_campaign(self, campaign_id: int) -> Optional[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_campaigns(self) -> list[dict]:
        cursor = await self._conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def create_business(self, campaign_id: int, name: str, website: str, phone: str = None,
                               address: str = None, rating: float = None, category: str = None,
                               city: str = None, country: str = None, place_id: str = None) -> int:
        cursor = await self._conn.execute(
            """INSERT INTO businesses
               (campaign_id, name, website, phone, address, rating, category, city, country, place_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (campaign_id, name, website, phone, address, rating, category, city, country, place_id),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_business(self, business_id: int) -> Optional[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM businesses WHERE id = ?", (business_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_businesses(self, campaign_id: int = None, country: str = None,
                              category: str = None, status: str = None) -> list[dict]:
        query = """SELECT b.*, a.status as audit_status, a.id as audit_id
                   FROM businesses b
                   LEFT JOIN audits a ON a.business_id = b.id
                   WHERE 1=1"""
        params = []
        if campaign_id is not None:
            query += " AND b.campaign_id = ?"
            params.append(campaign_id)
        if country:
            query += " AND b.country = ?"
            params.append(country)
        if category:
            query += " AND b.category = ?"
            params.append(category)
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY b.created_at DESC"
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def create_audit(self, business_id: int) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO audits (business_id, status) VALUES (?, 'pending')",
            (business_id,),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def update_audit_status(self, audit_id: int, status: str, error_message: str = None,
                                   lighthouse_json: str = None):
        query = "UPDATE audits SET status = ?, analyzed_at = CURRENT_TIMESTAMP"
        params = [status]
        if error_message:
            query += ", error_message = ?"
            params.append(error_message)
        if lighthouse_json:
            query += ", lighthouse_json = ?"
            params.append(lighthouse_json)
        query += " WHERE id = ?"
        params.append(audit_id)
        await self._conn.execute(query, params)
        await self._conn.commit()

    async def save_metric(self, audit_id: int, metric_name: str, score: float, details: str = None):
        await self._conn.execute(
            "INSERT OR REPLACE INTO audit_metrics (audit_id, metric_name, score, details) VALUES (?, ?, ?, ?)",
            (audit_id, metric_name, score, details),
        )
        await self._conn.commit()

    async def get_metrics(self, audit_id: int) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM audit_metrics WHERE audit_id = ?", (audit_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_summary(self) -> dict:
        result = {}
        cursor = await self._conn.execute("SELECT COUNT(*) as c FROM businesses")
        row = await cursor.fetchone()
        result["total_leads"] = row["c"]

        cursor = await self._conn.execute(
            "SELECT country, COUNT(*) as c FROM businesses GROUP BY country"
        )
        result["by_country"] = {r["country"]: r["c"] for r in await cursor.fetchall()}

        cursor = await self._conn.execute(
            "SELECT category, COUNT(*) as c FROM businesses GROUP BY category"
        )
        result["by_category"] = {r["category"]: r["c"] for r in await cursor.fetchall()}

        cursor = await self._conn.execute(
            """SELECT COUNT(*) as c FROM audits WHERE status = 'done'
               AND id IN (SELECT audit_id FROM audit_metrics WHERE metric_name = 'lead_score' AND score > 70)"""
        )
        row = await cursor.fetchone()
        result["urgent_leads"] = row["c"]

        cursor = await self._conn.execute(
            "SELECT COUNT(*) as c FROM audits WHERE status = 'pending'"
        )
        row = await cursor.fetchone()
        result["pending_audits"] = row["c"]

        return result

    async def delete_businesses(self, ids: list[int]):
        placeholders = ",".join("?" for _ in ids)
        await self._conn.execute(f"DELETE FROM audits WHERE business_id IN ({placeholders})", ids)
        await self._conn.execute(f"DELETE FROM businesses WHERE id IN ({placeholders})", ids)
        await self._conn.commit()
```

- [ ] **Step 3: Run tests**

Run: `pytest leadfinder/tests/test_database.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A; git commit -m "feat: add SQLite database module with CRUD operations"
```

---

### Task 3: Lead score calculation

**Files:**
- Create: `leadfinder/lead_score.py`
- Create: `leadfinder/tests/test_lead_score.py`

- [ ] **Step 1: Write the failing test**


```python
import pytest
from leadfinder.lead_score import calculate_lead_score


def test_perfect_site_scores_zero():
    score = calculate_lead_score(
        performance_score=100,
        seo_score=100,
        best_practices_score=100,
        mobile_friendly=1,
    )
    assert score == 0.0


def test_terrible_site_scores_high():
    score = calculate_lead_score(
        performance_score=10,
        seo_score=15,
        best_practices_score=20,
        mobile_friendly=0,
    )
    assert score > 70


def test_score_is_100_at_maximum():
    score = calculate_lead_score(
        performance_score=0,
        seo_score=0,
        best_practices_score=0,
        mobile_friendly=0,
    )
    assert score == 100.0


def test_mobile_friendly_contribution():
    with_mobile = calculate_lead_score(
        performance_score=50, seo_score=50, best_practices_score=50, mobile_friendly=1
    )
    without_mobile = calculate_lead_score(
        performance_score=50, seo_score=50, best_practices_score=50, mobile_friendly=0
    )
    assert without_mobile > with_mobile
    assert abs(without_mobile - with_mobile - 25.0) < 0.01


def test_score_never_exceeds_100():
    score = calculate_lead_score(
        performance_score=0, seo_score=0, best_practices_score=0, mobile_friendly=0
    )
    assert score <= 100.0
```

Run: `pytest leadfinder/tests/test_lead_score.py -v`
Expected: FAIL

- [ ] **Step 2: Write leadfinder/lead_score.py**

```python
def calculate_lead_score(
    performance_score: float = 50,
    seo_score: float = 50,
    best_practices_score: float = 50,
    mobile_friendly: int = 0,
) -> float:
    score = (
        (100 - performance_score) * 0.35
        + (100 - seo_score) * 0.25
        + (1 - mobile_friendly) * 25
        + (100 - best_practices_score) * 0.15
    )
    return round(min(score, 100.0), 1)
```

- [ ] **Step 3: Run tests**

Run: `pytest leadfinder/tests/test_lead_score.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A; git commit -m "feat: add lead score calculation"
```

---

### Task 4: Scraper module (Google Places API)

**Files:**
- Create: `leadfinder/scraper.py`
- Create: `leadfinder/tests/test_scraper.py`

- [ ] **Step 1: Write the failing test**


```python
import pytest
from unittest.mock import AsyncMock, patch
from leadfinder.scraper import Scraper


@pytest.mark.asyncio
async def test_run_scraper_returns_businesses():
    mock_response = {
        "results": [
            {
                "name": "Test Restaurant",
                "website": "https://test-restaurant.com",
                "formatted_phone_number": "+58 212 555 1234",
                "formatted_address": "Av. Principal, Caracas",
                "rating": 4.2,
                "types": ["restaurant", "food"],
                "place_id": "abc123",
            },
            {
                "name": "No Web Shop",
                "website": None,
                "place_id": "abc456",
            },
        ]
    }

    scraper = Scraper(api_key="fake-key")

    with patch.object(scraper, "_search_places", return_value=mock_response):
        with patch.object(scraper, "_get_place_details", return_value={}):
            businesses = await scraper.run(
                keyword="restaurantes",
                location="Caracas, Venezuela",
                radius=5000,
            )

    assert len(businesses) == 1
    assert businesses[0]["name"] == "Test Restaurant"
    assert businesses[0]["website"] == "https://test-restaurant.com"


@pytest.mark.asyncio
async def test_empty_results_returns_empty_list():
    scraper = Scraper(api_key="fake-key")

    with patch.object(scraper, "_search_places", return_value={"results": []}):
        businesses = await scraper.run(keyword="restaurantes", location="Caracas", radius=5000)

    assert businesses == []
```

Run: `pytest leadfinder/tests/test_scraper.py -v`
Expected: FAIL

- [ ] **Step 2: Write leadfinder/scraper.py**

```python
from typing import Optional
import googlemaps


class Scraper:
    def __init__(self, api_key: str):
        self._client = googlemaps.Client(key=api_key)

    async def run(self, keyword: str, location: str, radius: int = 5000,
                   min_rating: Optional[float] = None) -> list[dict]:
        businesses = []
        response = self._search_places(keyword, location, radius)

        for place in response.get("results", []):
            if not place.get("website") and not place.get("place_id"):
                continue

            details = self._get_place_details(place["place_id"])
            website = place.get("website") or details.get("website")
            if not website:
                continue

            if min_rating and (place.get("rating") or 0) < min_rating:
                continue

            businesses.append({
                "name": place["name"],
                "website": website,
                "phone": place.get("formatted_phone_number") or details.get("formatted_phone_number"),
                "address": place.get("formatted_address") or details.get("formatted_address"),
                "rating": place.get("rating"),
                "category": self._extract_category(place.get("types", [])),
                "city": self._extract_city(location),
                "country": self._extract_country(location),
                "place_id": place["place_id"],
            })

        return businesses

    def _search_places(self, keyword: str, location: str, radius: int) -> dict:
        return self._client.places(
            query=keyword,
            location=None,
            radius=radius,
            language="es",
        )

    def _get_place_details(self, place_id: str) -> dict:
        result = self._client.place(
            place_id=place_id,
            fields=["website", "formatted_phone_number", "formatted_address"],
        )
        return result.get("result", {})

    def _extract_category(self, types: list[str]) -> str:
        category_map = {
            "restaurant": "restaurante",
            "food": "restaurante",
            "cafe": "restaurante",
            "doctor": "clinica",
            "health": "clinica",
            "dentist": "clinica",
            "gym": "gimnasio",
            "car_repair": "taller",
            "lodging": "hotel",
            "real_estate_agency": "inmobiliaria",
            "store": "tienda",
            "shopping_mall": "tienda",
        }
        for t in types:
            if t in category_map:
                return category_map[t]
        return "otro"

    def _extract_city(self, location: str) -> str:
        return location.split(",")[0].strip() if "," in location else location.strip()

    def _extract_country(self, location: str) -> str:
        parts = [p.strip() for p in location.split(",")]
        return parts[-1] if len(parts) > 1 else ""
```

- [ ] **Step 3: Fix test to work with googlemaps sync API**


```python
import pytest
from unittest.mock import patch, MagicMock
from leadfinder.scraper import Scraper


@pytest.mark.asyncio
async def test_run_scraper_returns_businesses():
    scraper = Scraper(api_key="fake-key")

    mock_places_response = {
        "results": [
            {
                "name": "Test Restaurant",
                "website": "https://test-restaurant.com",
                "formatted_phone_number": "+58 212 555 1234",
                "formatted_address": "Av. Principal, Caracas",
                "rating": 4.2,
                "types": ["restaurant", "food"],
                "place_id": "abc123",
            },
            {
                "name": "No Web Shop",
                "website": None,
                "types": ["store"],
                "place_id": "abc456",
            },
        ]
    }

    with patch.object(scraper._client, "places", return_value=mock_places_response):
        with patch.object(scraper._client, "place", return_value={"result": {}}):
            businesses = await scraper.run(
                keyword="restaurantes",
                location="Caracas, Venezuela",
                radius=5000,
            )

    assert len(businesses) == 1
    assert businesses[0]["name"] == "Test Restaurant"
    assert businesses[0]["website"] == "https://test-restaurant.com"


@pytest.mark.asyncio
async def test_empty_results_returns_empty_list():
    scraper = Scraper(api_key="fake-key")

    with patch.object(scraper._client, "places", return_value={"results": []}):
        businesses = await scraper.run(keyword="restaurantes", location="Caracas", radius=5000)

    assert businesses == []
```

Run: `pytest leadfinder/tests/test_scraper.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A; git commit -m "feat: add Google Places API scraper"
```

---

### Task 5: Analyzer module (Lighthouse + HTML inspector)

**Files:**
- Create: `leadfinder/analyzer.py`
- Create: `leadfinder/tests/test_analyzer.py`

- [ ] **Step 1: Write the failing test**


```python
import pytest
from unittest.mock import patch, AsyncMock
from leadfinder.analyzer import Analyzer


@pytest.mark.asyncio
async def test_analyze_returns_metrics():
    with patch("leadfinder.analyzer.Analyzer._run_lighthouse") as mock_lh:
        mock_lh.return_value = {
            "categories": {
                "performance": {"score": 0.45},
                "accessibility": {"score": 0.78},
                "seo": {"score": 0.60},
                "best-practices": {"score": 0.90},
            }
        }
        with patch("leadfinder.analyzer.Analyzer._inspect_html") as mock_html:
            mock_html.return_value = {
                "mobile_friendly": 1,
                "has_meta_description": 1,
                "has_open_graph": 0,
                "has_ssl": 1,
                "technologies": "WordPress",
            }
            analyzer = Analyzer()
            metrics = await analyzer.analyze("https://test-restaurant.com")

    assert metrics["performance_score"] == 45.0
    assert metrics["seo_score"] == 60.0
    assert metrics["mobile_friendly"] == 1
    assert metrics["technologies"] == "WordPress"
    assert "lead_score" in metrics


@pytest.mark.asyncio
async def test_analyze_handles_http_error():
    with patch("leadfinder.analyzer.Analyzer._run_lighthouse") as mock_lh:
        mock_lh.side_effect = Exception("Connection failed")
        analyzer = Analyzer()
        with pytest.raises(RuntimeError, match="Connection failed"):
            await analyzer.analyze("https://broken-site.com")
```

Run: `pytest leadfinder/tests/test_analyzer.py -v`
Expected: FAIL

- [ ] **Step 2: Write leadfinder/analyzer.py**

```python
import json
import subprocess
import asyncio
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from leadfinder.lead_score import calculate_lead_score


class Analyzer:
    async def analyze(self, url: str) -> dict:
        lh_result, html_result = await asyncio.gather(
            self._run_lighthouse(url),
            self._inspect_html(url),
        )

        metrics = {}
        for category, data in lh_result.get("categories", {}).items():
            if category == "best-practices":
                metrics["best_practices_score"] = round(data.get("score", 0) * 100, 1)
            else:
                metrics[f"{category}_score"] = round(data.get("score", 0) * 100, 1)

        metrics.update(html_result)

        metrics["lead_score"] = calculate_lead_score(
            performance_score=metrics.get("performance_score", 50),
            seo_score=metrics.get("seo_score", 50),
            best_practices_score=metrics.get("best_practices_score", 50),
            mobile_friendly=metrics.get("mobile_friendly", 0),
        )

        return metrics

    async def _run_lighthouse(self, url: str) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                "lighthouse", url,
                "--chrome-flags=--headless",
                "--output=json",
                "--quiet",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode != 0:
                raise RuntimeError(f"Lighthouse failed: {stderr.decode()[:500]}")
            return json.loads(stdout.decode())
        except FileNotFoundError:
            raise RuntimeError("Lighthouse not found. Install: npm install -g lighthouse")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Lighthouse timed out for {url}")

    async def _inspect_html(self, url: str) -> dict:
        result = {
            "mobile_friendly": 0,
            "has_meta_description": 0,
            "has_open_graph": 0,
            "has_ssl": 0,
            "technologies": "",
        }

        parsed = urlparse(url)
        if parsed.scheme == "https":
            result["has_ssl"] = 1

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return result

                soup = BeautifulSoup(response.text, "html.parser")

                meta_viewport = soup.find("meta", attrs={"name": "viewport"})
                if meta_viewport:
                    result["mobile_friendly"] = 1

                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content", "").strip():
                    result["has_meta_description"] = 1

                og_tags = soup.find_all("meta", attrs={"property": lambda x: x and x.startswith("og:")})
                if og_tags:
                    result["has_open_graph"] = 1

                technologies = []
                generator = soup.find("meta", attrs={"name": "generator"})
                if generator:
                    gen = generator.get("content", "")
                    if "wordpress" in gen.lower():
                        technologies.append("WordPress")
                    elif "wix" in gen.lower():
                        technologies.append("Wix")
                    elif "shopify" in gen.lower():
                        technologies.append("Shopify")
                    elif "joomla" in gen.lower():
                        technologies.append("Joomla")
                    elif "drupal" in gen.lower():
                        technologies.append("Drupal")

                if not technologies:
                    scripts = soup.find_all("script", src=True)
                    for script in scripts:
                        src = script.get("src", "")
                        if "wp-content" in src or "wp-includes" in src:
                            technologies.append("WordPress")
                            break
                        if "wixstatic" in src:
                            technologies.append("Wix")
                            break
                        if "shopify" in src:
                            technologies.append("Shopify")
                            break

                result["technologies"] = ", ".join(technologies)

        except httpx.RequestError:
            pass

        return result
```

- [ ] **Step 3: Run tests**

Run: `pytest leadfinder/tests/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A; git commit -m "feat: add Lighthouse + HTML analyzer"
```

---

### Task 6: Web app bootstrap + base template

**Files:**
- Create: `leadfinder/web/__init__.py`
- Create: `leadfinder/web/app.py`
- Create: `leadfinder/web/templates/base.html`

- [ ] **Step 1: Write leadfinder/web/__init__.py** (empty)

```python
```

- [ ] **Step 2: Write leadfinder/web/app.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from leadfinder.database import Database
from leadfinder.config import settings

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
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
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "summary": summary,
    })


@app.get("/leads", response_class=HTMLResponse)
async def leads(request: Request, country: str = "", category: str = "",
               min_score: float = 0, status: str = ""):
    businesses = await db.get_businesses(country=country or None, category=category or None, status=status or None)
    enriched = []
    for b in businesses:
        if b.get("audit_id"):
            metrics = await db.get_metrics(b["audit_id"])
            score = next((m["score"] for m in metrics if m["metric_name"] == "lead_score"), None)
            b["lead_score"] = score
            b["metrics"] = {m["metric_name"]: m["score"] for m in metrics}
        enriched.append(b)
    if min_score > 0:
        enriched = [b for b in enriched if (b.get("lead_score") or 0) >= min_score]
    enriched.sort(key=lambda b: b.get("lead_score") or 0, reverse=True)
    return templates.TemplateResponse("leads.html", {
        "request": request,
        "leads": enriched,
    })


@app.get("/leads/{lead_id}", response_class=HTMLResponse)
async def lead_detail(request: Request, lead_id: int):
    business = await db.get_business(lead_id)
    if not business:
        return HTMLResponse("Not found", status_code=404)
    metrics_list = []
    if business.get("audit_id"):
        metrics_list = await db.get_metrics(business["audit_id"])
    metrics_dict = {m["metric_name"]: m for m in metrics_list}
    return templates.TemplateResponse("lead_detail.html", {
        "request": request,
        "lead": business,
        "metrics": metrics_dict,
    })


@app.post("/leads/bulk-delete")
async def bulk_delete(ids: list[int] = Form(...)):
    await db.delete_businesses(ids)
    return HTMLResponse("Deleted")


@app.get("/leads/export")
async def export_leads():
    businesses = await db.get_businesses()
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "website", "phone", "address", "rating", "category", "city", "country"])
    for b in businesses:
        writer.writerow([b["name"], b["website"], b["phone"], b["address"],
                         b["rating"], b["category"], b["city"], b["country"]])
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns(request: Request):
    all_campaigns = await db.get_campaigns()
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "campaigns": all_campaigns,
    })


@app.post("/campaigns/new")
async def new_campaign(request: Request, name: str = Form(...), keyword: str = Form(...),
                        location: str = Form(...), country: str = Form("Venezuela"),
                        radius: int = Form(5000)):
    from leadfinder.scraper import Scraper
    from leadfinder.config import settings

    if not settings.google_places_api_key:
        return HTMLResponse("GOOGLE_PLACES_API_KEY not configured", status_code=400)

    campaign_id = await db.create_campaign(name=name, keyword=keyword, location=location, country=country)
    scraper = Scraper(api_key=settings.google_places_api_key)
    businesses = await scraper.run(keyword=keyword, location=location, radius=radius)
    for b in businesses:
        bid = await db.create_business(campaign_id=campaign_id, **b)
        await db.create_audit(business_id=bid)
    return HTMLResponse(f"""<div hx-get="/campaigns/{campaign_id}" hx-trigger="load" hx-swap="outerHTML"></div>""")


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int):
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        return HTMLResponse("Not found", status_code=404)
    businesses = await db.get_businesses(campaign_id=campaign_id)
    return templates.TemplateResponse("campaign_detail.html", {
        "request": request,
        "campaign": campaign,
        "businesses": businesses,
    })


@app.post("/campaigns/{campaign_id}/analyze")
async def analyze_campaign(campaign_id: int):
    from leadfinder.analyzer import Analyzer
    businesses = await db.get_businesses(campaign_id=campaign_id)
    analyzer = Analyzer()
    errors = []
    for b in businesses:
        audits = await db._conn.execute(
            "SELECT id FROM audits WHERE business_id = ? AND status = 'pending'", (b["id"],)
        )
        row = await audits.fetchone()
        if not row:
            continue
        audit_id = row["id"]
        await db.update_audit_status(audit_id, "running")
        try:
            metrics = await analyzer.analyze(b["website"])
            for key, value in metrics.items():
                details = None
                score = value
                if key == "technologies":
                    details = value
                    score = 0
                await db.save_metric(audit_id=audit_id, metric_name=key, score=score if isinstance(score, (int, float)) else 0, details=details)
            await db.update_audit_status(audit_id, "done")
        except Exception as e:
            await db.update_audit_status(audit_id, "error", error_message=str(e))
            errors.append(f"{b['name']}: {e}")
    if errors:
        return HTMLResponse(f"Completed with {len(errors)} errors:\n" + "\n".join(errors))
    return HTMLResponse("Analysis complete")
```

- [ ] **Step 3: Write base.html template**

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LeadFinder</title>
    <script src="https://unpkg.com/htmx.org@2.0.0"></script>
    <script defer src="https://unpkg.com/alpinejs@3.14.0"></script>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="flex">
        <nav class="w-64 bg-white shadow-sm min-h-screen p-4">
            <h1 class="text-xl font-bold text-gray-800 mb-6">LeadFinder</h1>
            <ul class="space-y-2">
                <li><a href="/" class="block px-3 py-2 rounded hover:bg-gray-100 text-gray-700">Dashboard</a></li>
                <li><a href="/leads" class="block px-3 py-2 rounded hover:bg-gray-100 text-gray-700">Leads</a></li>
                <li><a href="/campaigns" class="block px-3 py-2 rounded hover:bg-gray-100 text-gray-700">Campañas</a></li>
            </ul>
        </nav>
        <main class="flex-1 p-6">
            {% block content %}{% endblock %}
        </main>
    </div>
</body>
</html>
```

- [ ] **Step 4: Commit**

```bash
git add -A; git commit -m "feat: add FastAPI server and base template"
```

---

### Task 7: Web templates — Dashboard + Campaigns

**Files:**
- Create: `leadfinder/web/templates/dashboard.html`
- Create: `leadfinder/web/templates/campaigns.html`
- Create: `leadfinder/web/templates/campaign_detail.html`

- [ ] **Step 1: Write dashboard.html**

```html
{% extends "base.html" %}
{% block content %}
<h2 class="text-2xl font-bold mb-4">Dashboard</h2>
<div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
    <div class="bg-white p-4 rounded shadow">
        <div class="text-3xl font-bold text-blue-600">{{ summary.total_leads }}</div>
        <div class="text-gray-500 text-sm">Total Leads</div>
    </div>
    <div class="bg-white p-4 rounded shadow">
        <div class="text-3xl font-bold text-red-600">{{ summary.urgent_leads }}</div>
        <div class="text-gray-500 text-sm">Urgentes (score > 70)</div>
    </div>
    <div class="bg-white p-4 rounded shadow">
        <div class="text-3xl font-bold text-yellow-600">{{ summary.pending_audits }}</div>
        <div class="text-gray-500 text-sm">Pendientes de Análisis</div>
    </div>
    <div class="bg-white p-4 rounded shadow">
        <div class="text-3xl font-bold text-green-600">{{ summary.total_leads - summary.urgent_leads }}</div>
        <div class="text-gray-500 text-sm">No Urgentes</div>
    </div>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="bg-white p-4 rounded shadow">
        <h3 class="font-semibold mb-2">Por País</h3>
        <ul>
            {% for country, count in (summary.by_country or {}).items() %}
            <li class="flex justify-between py-1 border-b">{{ country }} <span class="font-bold">{{ count }}</span></li>
            {% endfor %}
        </ul>
    </div>
    <div class="bg-white p-4 rounded shadow">
        <h3 class="font-semibold mb-2">Por Categoría</h3>
        <ul>
            {% for cat, count in (summary.by_category or {}).items() %}
            <li class="flex justify-between py-1 border-b">{{ cat }} <span class="font-bold">{{ count }}</span></li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Write campaigns.html**

```html
{% extends "base.html" %}
{% block content %}
<h2 class="text-2xl font-bold mb-4">Campañas</h2>

<form hx-post="/campaigns/new" hx-target="#campaign-list" class="bg-white p-4 rounded shadow mb-6">
    <h3 class="font-semibold mb-3">Nueva Campaña</h3>
    <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
        <input type="text" name="name" placeholder="Nombre" required class="border p-2 rounded">
        <input type="text" name="keyword" placeholder="keyword (ej: restaurantes)" required class="border p-2 rounded">
        <input type="text" name="location" placeholder="Ciudad, País" required class="border p-2 rounded">
        <select name="country" class="border p-2 rounded">
            <option value="Venezuela">Venezuela</option>
            <option value="Uruguay">Uruguay</option>
        </select>
        <button type="submit" class="bg-blue-600 text-white p-2 rounded hover:bg-blue-700">Crear + Scrapear</button>
    </div>
</form>

<div id="campaign-list">
    <div class="bg-white rounded shadow">
        {% for campaign in campaigns %}
        <div class="p-4 border-b hover:bg-gray-50">
            <a href="/campaigns/{{ campaign.id }}" class="font-semibold text-blue-600">{{ campaign.name }}</a>
            <div class="text-sm text-gray-500">{{ campaign.keyword }} — {{ campaign.location }}</div>
            <div class="text-xs text-gray-400">{{ campaign.created_at }}</div>
        </div>
        {% else %}
        <div class="p-4 text-gray-500">No hay campañas aún</div>
        {% endfor %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Write campaign_detail.html**

```html
{% extends "base.html" %}
{% block content %}
<h2 class="text-2xl font-bold mb-2">{{ campaign.name }}</h2>
<p class="text-gray-500 mb-4">{{ campaign.keyword }} — {{ campaign.location }} ({{ campaign.country }})</p>

<button hx-post="/campaigns/{{ campaign.id }}/analyze" hx-target="#result"
        class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 mb-4">
    Analizar Todos
</button>
<div id="result" class="mb-4"></div>

<div class="bg-white rounded shadow">
    <table class="w-full">
        <thead>
            <tr class="border-b bg-gray-50">
                <th class="text-left p-3">Nombre</th>
                <th class="text-left p-3">Web</th>
                <th class="text-left p-3">Rating</th>
                <th class="text-left p-3">Estado</th>
            </tr>
        </thead>
        <tbody>
            {% for b in businesses %}
            <tr class="border-b hover:bg-gray-50">
                <td class="p-3"><a href="/leads/{{ b.id }}" class="text-blue-600">{{ b.name }}</a></td>
                <td class="p-3 text-sm">{{ b.website }}</td>
                <td class="p-3">{{ b.rating or '-' }}</td>
                <td class="p-3">{{ b.audit_status or 'pending' }}</td>
            </tr>
            {% else %}
            <tr><td colspan="4" class="p-3 text-gray-500">Sin leads aún</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add -A; git commit -m "feat: add dashboard and campaigns templates"
```

---

### Task 8: Web templates — Leads + Lead Detail

**Files:**
- Create: `leadfinder/web/templates/leads.html`
- Create: `leadfinder/web/templates/lead_detail.html`

- [ ] **Step 1: Write leads.html**

```html
{% extends "base.html" %}
{% block content %}
<h2 class="text-2xl font-bold mb-4">Leads</h2>

<div class="bg-white p-4 rounded shadow mb-4 flex gap-3" x-data="{ country: '', category: '', minScore: 0, status: '' }">
    <select x-model="country" @change="$dispatch('filter')" class="border p-2 rounded">
        <option value="">Todos los países</option>
        <option value="Venezuela">Venezuela</option>
        <option value="Uruguay">Uruguay</option>
    </select>
    <select x-model="category" @change="$dispatch('filter')" class="border p-2 rounded">
        <option value="">Todas las categorías</option>
        <option value="restaurante">Restaurante</option>
        <option value="clinica">Clínica</option>
        <option value="taller">Taller</option>
        <option value="gimnasio">Gimnasio</option>
        <option value="hotel">Hotel</option>
        <option value="inmobiliaria">Inmobiliaria</option>
        <option value="tienda">Tienda</option>
        <option value="otro">Otro</option>
    </select>
    <select x-model="minScore" @change="$dispatch('filter')" class="border p-2 rounded">
        <option value="0">Todos los scores</option>
        <option value="70">Urgentes (>70)</option>
        <option value="40">Medios (>40)</option>
    </select>
    <select x-model="status" @change="$dispatch('filter')" class="border p-2 rounded">
        <option value="">Todos los estados</option>
        <option value="pending">Pendiente</option>
        <option value="done">Analizado</option>
        <option value="error">Error</option>
    </select>
    <a href="/leads/export" class="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700 ml-auto">Exportar CSV</a>
</div>

<div id="leads-table" hx-get="/leads" hx-trigger="filter from:window" hx-target="#leads-table"
     hx-include="select[name]">
    <div class="bg-white rounded shadow overflow-x-auto">
        <table class="w-full">
            <thead>
                <tr class="border-b bg-gray-50">
                    <th class="text-left p-3">Nombre</th>
                    <th class="text-left p-3">Web</th>
                    <th class="text-left p-3">País</th>
                    <th class="text-left p-3">Categoría</th>
                    <th class="text-left p-3">Score</th>
                    <th class="text-left p-3">Estado</th>
                </tr>
            </thead>
            <tbody>
                {% for lead in leads %}
                <tr class="border-b hover:bg-gray-50">
                    <td class="p-3"><a href="/leads/{{ lead.id }}" class="text-blue-600">{{ lead.name }}</a></td>
                    <td class="p-3 text-sm truncate max-w-xs">{{ lead.website }}</td>
                    <td class="p-3">{{ lead.country }}</td>
                    <td class="p-3">{{ lead.category }}</td>
                    <td class="p-3">
                        {% if lead.lead_score is not none %}
                        <span class="px-2 py-1 rounded text-white text-sm
                            {% if lead.lead_score > 70 %}bg-red-500
                            {% elif lead.lead_score > 40 %}bg-yellow-500
                            {% else %}bg-green-500{% endif %}">
                            {{ "%.0f"|format(lead.lead_score) }}
                        </span>
                        {% else %}
                        <span class="text-gray-400">-</span>
                        {% endif %}
                    </td>
                    <td class="p-3">{{ lead.audit_status or 'pending' }}</td>
                </tr>
                {% else %}
                <tr><td colspan="6" class="p-3 text-gray-500">No hay leads aún</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Write lead_detail.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="bg-white p-6 rounded shadow">
    <h2 class="text-2xl font-bold mb-2">{{ lead.name }}</h2>
    <p class="text-gray-500 mb-4">{{ lead.address }} — {{ lead.city }}, {{ lead.country }}</p>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
            <p><strong>Web:</strong> <a href="{{ lead.website }}" target="_blank" class="text-blue-600">{{ lead.website }}</a></p>
            <p><strong>Teléfono:</strong> {{ lead.phone or '-' }}</p>
            <p><strong>Rating Google:</strong> {{ lead.rating or '-' }}</p>
            <p><strong>Categoría:</strong> {{ lead.category or '-' }}</p>
        </div>
        <div>
            {% if metrics %}
            <p><strong>Lead Score:</strong>
                <span class="px-2 py-1 rounded text-white
                    {% if metrics.lead_score.score > 70 %}bg-red-500
                    {% elif metrics.lead_score.score > 40 %}bg-yellow-500
                    {% else %}bg-green-500{% endif %}">
                    {{ "%.0f"|format(metrics.lead_score.score) }}
                </span>
            </p>
            {% endif %}
        </div>
    </div>

    {% if metrics %}
    <h3 class="font-semibold text-lg mb-2">Métricas de Auditoría</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {% for key, label in [('performance_score', 'Performance'), ('seo_score', 'SEO'),
                              ('best_practices_score', 'Best Practices'), ('accessibility_score', 'Accesibilidad')] %}
        {% if key in metrics %}
        <div class="bg-gray-50 p-3 rounded">
            <div class="text-sm text-gray-500">{{ label }}</div>
            <div class="text-xl font-bold">{{ "%.0f"|format(metrics[key].score) }}</div>
        </div>
        {% endif %}
        {% endfor %}
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {% for key, label in [('mobile_friendly', 'Mobile Friendly'), ('has_meta_description', 'Meta Desc'),
                              ('has_open_graph', 'Open Graph'), ('has_ssl', 'HTTPS')] %}
        {% if key in metrics %}
        <div class="bg-gray-50 p-3 rounded">
            <div class="text-sm text-gray-500">{{ label }}</div>
            <div class="text-xl">
                {% if metrics[key].score == 1 %}✅{% else %}❌{% endif %}
            </div>
        </div>
        {% endif %}
        {% endfor %}
    </div>

    {% if metrics.technologies and metrics.technologies.details %}
    <p><strong>Tecnologías:</strong> {{ metrics.technologies.details }}</p>
    {% endif %}
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add -A; git commit -m "feat: add leads list and detail templates"
```

---

### Task 9: CLI entry point

**Files:**
- Create: `leadfinder/__main__.py`

- [ ] **Step 1: Write leadfinder/__main__.py**

```python
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
    run_parser.add_argument("--campaign", required=True, help="Campaign name")
    run_parser.add_argument("--keyword", required=True, help="Search keyword")
    run_parser.add_argument("--location", required=True, help="Location (City, Country)")
    run_parser.add_argument("--country", default="Venezuela", help="Country")
    run_parser.add_argument("--radius", type=int, default=5000, help="Search radius in meters")
    run_parser.add_argument("--analyze", action="store_true", help="Run analysis after scraping")

    serve_parser = subparsers.add_parser("serve", help="Start the web dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port")

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
        name=args.campaign,
        keyword=args.keyword,
        location=args.location,
        country=args.country,
    )
    print(f"Created campaign #{campaign_id}: {args.campaign}")

    scraper = Scraper(api_key=settings.google_places_api_key)
    businesses = await scraper.run(
        keyword=args.keyword,
        location=args.location,
        radius=args.radius,
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
            bid = await db.get_businesses(campaign_id=campaign_id)
            bid_entry = next((x for x in bid if x["website"] == b["website"]), None)
            if not bid_entry:
                continue
            cursor = await db._conn.execute(
                "SELECT id FROM audits WHERE business_id = ?", (bid_entry["id"],)
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
                    details = value if key == "technologies" else None
                    await db.save_metric(audit_id=audit_id, metric_name=key, score=score, details=details)
                await db.update_audit_status(audit_id, "done")
                lead = metrics.get("lead_score", "N/A")
                print(f"    Done — Lead Score: {lead}")
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
```

- [ ] **Step 2: Install dependencies and verify** (manual test)

```bash
cd leadfinder; pip install -r requirements.txt
python -m leadfinder serve --port 8000
```

Verify: Open http://127.0.0.1:8000/ in browser → Dashboard should load

- [ ] **Step 3: Commit**

```bash
git add -A; git commit -m "feat: add CLI entry point (run + serve)"
```

---

### Task 10: Integration smoke test

- [ ] **Step 1: Run the full test suite**

```bash
pytest leadfinder/tests/ -v
```

Expected: All tests pass

- [ ] **Step 2: Start the web server**

```bash
python -m leadfinder serve
```

Verify: Server starts on port 8000

- [ ] **Step 3: Commit**

```bash
git add -A; git commit -m "chore: final adjustments after integration test"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Every element from spec has a task — database (Task 2), scoring (Task 3), scraper (Task 4), analyzer (Task 5), dashboard routes (Task 6), templates (Tasks 7-8), CLI (Task 9)
- [x] **Placeholder scan:** No "TBD", "TODO", "implement later" in the plan
- [x] **Type consistency:** All function signatures and model fields are consistent across tasks
- [x] **Scope:** Focused on a single subsystem (the scraper tool itself, not a SaaS product)
