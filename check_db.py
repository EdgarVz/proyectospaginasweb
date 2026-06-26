import asyncio
from leadfinder.database import Database
from leadfinder.config import settings
async def main():
    db = Database(settings.database_path)
    await db.initialize()
    bizes = await db.get_businesses(campaign_id=1)
    for b in bizes:
        cur = await db._conn.execute('SELECT id, status FROM audits WHERE business_id = ?', (b['id'],))
        row = await cur.fetchone()
        name = b['name'][:38]
        website = b['website'][:38]
        print(f'{name:40s} website={website:40s} audit={row}')
    await db.close()
asyncio.run(main())
