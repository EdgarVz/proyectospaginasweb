import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from leadfinder.scraper import Scraper


@pytest_asyncio.fixture
def mock_googlemaps():
    with patch("leadfinder.scraper.googlemaps") as mock:
        mock_client = MagicMock()
        mock.Client.return_value = mock_client
        yield mock_client


@pytest_asyncio.fixture
async def scraper(mock_googlemaps):
    return Scraper(api_key="fake-key")


def _make_place_result(place_id, name, rating=4.0, types=None, website=None,
                       phone=None, address=None):
    return {
        "place_id": place_id,
        "name": name,
        "rating": rating,
        "types": types or ["restaurant", "point_of_interest", "establishment"],
    }


def _make_place_detail(website=None, phone=None, address=None,
                       address_components=None):
    result = {}
    if website is not None:
        result["website"] = website
    if phone is not None:
        result["formatted_phone_number"] = phone
    if address is not None:
        result["formatted_address"] = address
    if address_components is not None:
        result["address_components"] = address_components
    return {"result": result}


@pytest.mark.asyncio
async def test_scraper_returns_businesses_with_websites(scraper, mock_googlemaps):
    mock_googlemaps.places.return_value = {
        "results": [
            _make_place_result("place_1", "Business One", types=[
                "restaurant", "point_of_interest", "establishment"
            ]),
            _make_place_result("place_2", "Business Two"),
        ],
        "status": "OK",
    }

    def place_side_effect(place_id, fields):
        details = {
            "place_1": {"result": {
                "website": "https://business-one.com",
                "formatted_phone_number": "+58 212 555 0001",
                "formatted_address": "Av. Principal, Caracas, Venezuela",
                "address_components": [
                    {"long_name": "Caracas", "short_name": "Caracas",
                     "types": ["locality", "political"]},
                    {"long_name": "Venezuela", "short_name": "VE",
                     "types": ["country", "political"]},
                ],
            }},
            "place_2": {"result": {
                "website": None,
                "formatted_phone_number": "+58 212 555 0002",
                "formatted_address": "Calle 2, Caracas, Venezuela",
                "address_components": [
                    {"long_name": "Caracas", "short_name": "Caracas",
                     "types": ["locality", "political"]},
                    {"long_name": "Venezuela", "short_name": "VE",
                     "types": ["country", "political"]},
                ],
            }},
        }
        return details[place_id]
    mock_googlemaps.place.side_effect = place_side_effect

    results = await scraper.run(keyword="restaurantes", location="Caracas")

    assert len(results) == 1
    assert results[0]["name"] == "Business One"
    assert results[0]["website"] == "https://business-one.com"
    assert results[0]["phone"] == "+58 212 555 0001"
    assert results[0]["address"] == "Av. Principal, Caracas, Venezuela"
    assert results[0]["rating"] == 4.0
    assert results[0]["category"] == "restaurant"
    assert results[0]["city"] == "Caracas"
    assert results[0]["country"] == "Venezuela"
    assert results[0]["place_id"] == "place_1"


@pytest.mark.asyncio
async def test_scraper_skips_businesses_without_website(scraper, mock_googlemaps):
    mock_googlemaps.places.return_value = {
        "results": [
            _make_place_result("place_1", "No Web Business"),
        ],
        "status": "OK",
    }
    mock_googlemaps.place.return_value = {
        "result": {
            "formatted_phone_number": "+58 212 555 0001",
            "formatted_address": "Av. Principal, Caracas, Venezuela",
            "address_components": [
                {"long_name": "Caracas", "short_name": "Caracas",
                 "types": ["locality", "political"]},
                {"long_name": "Venezuela", "short_name": "VE",
                 "types": ["country", "political"]},
            ],
        }
    }

    results = await scraper.run(keyword="restaurantes", location="Caracas")

    assert results == []


@pytest.mark.asyncio
async def test_scraper_empty_results_returns_empty_list(scraper, mock_googlemaps):
    mock_googlemaps.places.return_value = {"results": [], "status": "OK"}

    results = await scraper.run(keyword="nonexistent", location="Nowhere")

    assert results == []


@pytest.mark.asyncio
async def test_scraper_filters_by_min_rating(scraper, mock_googlemaps):
    mock_googlemaps.places.return_value = {
        "results": [
            _make_place_result("place_1", "High Rated", rating=4.5),
            _make_place_result("place_2", "Low Rated", rating=2.0),
        ],
        "status": "OK",
    }

    def place_side_effect(place_id, fields):
        details = {
            "place_1": {"result": {
                "website": "https://high-rated.com",
                "formatted_phone_number": "+58 212 555 0001",
                "formatted_address": "Av. A, Caracas, Venezuela",
                "address_components": [
                    {"long_name": "Caracas", "short_name": "Caracas",
                     "types": ["locality", "political"]},
                    {"long_name": "Venezuela", "short_name": "VE",
                     "types": ["country", "political"]},
                ],
            }},
            "place_2": {"result": {
                "website": "https://low-rated.com",
                "formatted_phone_number": "+58 212 555 0002",
                "formatted_address": "Av. B, Caracas, Venezuela",
                "address_components": [
                    {"long_name": "Caracas", "short_name": "Caracas",
                     "types": ["locality", "political"]},
                    {"long_name": "Venezuela", "short_name": "VE",
                     "types": ["country", "political"]},
                ],
            }},
        }
        return details[place_id]
    mock_googlemaps.place.side_effect = place_side_effect

    results = await scraper.run(keyword="restaurantes", location="Caracas",
                                min_rating=3.0)

    assert len(results) == 1
    assert results[0]["name"] == "High Rated"


@pytest.mark.asyncio
async def test_scraper_passes_radius_to_places(scraper, mock_googlemaps):
    mock_googlemaps.places.return_value = {"results": [], "status": "OK"}

    await scraper.run(keyword="test", location="City", radius=10000)

    mock_googlemaps.places.assert_called_once_with(
        query="test", location=None, radius=10000, language="es"
    )


@pytest.mark.asyncio
async def test_scraper_category_maps_types(scraper, mock_googlemaps):
    mock_googlemaps.places.return_value = {
        "results": [
            _make_place_result("p1", "Dentist", types=[
                "dentist", "health", "point_of_interest", "establishment"
            ]),
        ],
        "status": "OK",
    }
    mock_googlemaps.place.return_value = {
        "result": {
            "website": "https://dentist.com",
            "formatted_phone_number": "+58 212 555 0001",
            "formatted_address": "Av. C, Caracas, Venezuela",
            "address_components": [
                {"long_name": "Caracas", "short_name": "Caracas",
                 "types": ["locality", "political"]},
                {"long_name": "Venezuela", "short_name": "VE",
                 "types": ["country", "political"]},
            ],
        }
    }

    results = await scraper.run(keyword="dentist", location="Caracas")

    assert len(results) == 1
    assert results[0]["category"] == "dentist"
