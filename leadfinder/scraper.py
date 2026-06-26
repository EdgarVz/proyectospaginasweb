import googlemaps

_GENERIC_TYPES = {"point_of_interest", "establishment", "political"}


class Scraper:
    def __init__(self, api_key: str):
        self._client = googlemaps.Client(key=api_key)

    async def run(self, keyword: str, location: str, radius: int = 5000,
                  min_rating: float | None = None) -> list[dict]:
        places_resp = self._client.places(
            query=keyword, location=None, radius=radius, language="es"
        )
        results = places_resp.get("results", [])

        businesses = []
        for place in results:
            detail = self._client.place(
                place_id=place["place_id"],
                fields=["website", "formatted_phone_number", "formatted_address", "address_component"],
            )
            detail_result = detail.get("result", {})

            website = detail_result.get("website")
            if not website:
                continue

            rating = place.get("rating")
            if min_rating is not None and (rating is None or rating < min_rating):
                continue

            address_components = detail_result.get("address_component", [])

            businesses.append({
                "name": place.get("name", ""),
                "website": website,
                "phone": detail_result.get("formatted_phone_number", ""),
                "address": detail_result.get("formatted_address", ""),
                "rating": rating,
                "category": self._map_category(place.get("types", [])),
                "city": self._extract_city(address_components),
                "country": self._extract_country(address_components),
                "place_id": place["place_id"],
            })

        return businesses

    def _map_category(self, types: list[str]) -> str:
        for t in types:
            if t not in _GENERIC_TYPES:
                return t
        return ""

    def _extract_city(self, components: list[dict]) -> str:
        for c in components:
            if "locality" in c.get("types", []):
                return c.get("long_name", "")
        return ""

    def _extract_country(self, components: list[dict]) -> str:
        for c in components:
            if "country" in c.get("types", []):
                return c.get("long_name", "")
        return ""
