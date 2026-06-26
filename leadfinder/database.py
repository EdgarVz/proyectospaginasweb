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
            place_id    TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id     INTEGER NOT NULL REFERENCES businesses(id),
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
