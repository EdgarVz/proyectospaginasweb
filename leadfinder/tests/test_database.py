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
