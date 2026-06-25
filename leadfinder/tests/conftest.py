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
