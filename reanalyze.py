import asyncio, sqlite3
from leadfinder.database import Database
from leadfinder.analyzer import Analyzer
from leadfinder.config import settings

async def main():
    db = Database(settings.database_path)
    await db.initialize()
    # reset all audits to pending
    await db._conn.execute("UPDATE audits SET status = 'pending', error_message = NULL")
    await db._conn.commit()
    bizes = await db.get_businesses()
    analyzer = Analyzer()
    for b in bizes:
        cur = await db._conn.execute("SELECT id FROM audits WHERE business_id = ?", (b['id'],))
        row = await cur.fetchone()
        aid = row['id']
        name = b['name'][:40]
        print(f'Analyzing {name} - {b["website"]}...')
        await db.update_audit_status(aid, 'running')
        try:
            metrics = await analyzer.analyze(b['website'])
            for k, v in metrics.items():
                score = v if isinstance(v, (int, float)) else 0
                det = str(v) if k == 'technologies' else None
                await db.save_metric(aid, k, score, det)
            await db.update_audit_status(aid, 'done')
            print(f'  OK - Lead Score: {metrics.get("lead_score", "?")}')
        except Exception as e:
            await db.update_audit_status(aid, 'error', str(e))
            print(f'  ERROR: {e}')
    await db.close()

asyncio.run(main())
