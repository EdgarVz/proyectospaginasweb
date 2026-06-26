import googlemaps

_GENERIC_TYPES = {"point_of_interest", "establishment", "political"}


class Scraper:
    def __init__(self, api_key: str):
        self._client = googlemaps.Client(key=api_key)

    async def run(self, keyword: str, location: str, radius: int = 5000,
                  min_rating: float | None = None,
                  exclude_domains: list[str] | None = None,
                  broad: bool = False) -> list[dict]:
        keywords = [k.strip() for k in keyword.split(",") if k.strip()] if not broad else [None]
        geo = self._client.geocode(location)
        loc = geo[0]["geometry"]["location"] if geo else None
        seen_place_ids = set()
        businesses = []
        for kw in keywords:
            if broad or kw is None:
                if not loc:
                    continue
                places_resp = self._client.places_nearby(
                    location=(loc["lat"], loc["lng"]),
                    radius=radius, type="establishment", language="es",
                )
            else:
                places_resp = self._client.places(
                    query=kw,
                    location=(loc["lat"], loc["lng"]) if loc else None,
                    radius=radius, language="es",
                )
            results = places_resp.get("results", [])
            for place in results:
                pid = place["place_id"]
                if pid in seen_place_ids:
                    continue
                seen_place_ids.add(pid)
                biz = self._enrich_place(place, min_rating, exclude_domains)
                if biz:
                    businesses.append(biz)
        return businesses

    def _enrich_place(self, place: dict, min_rating: float | None,
                      exclude_domains: list[str] | None) -> dict | None:
        detail = self._client.place(
            place_id=place["place_id"],
            fields=["website", "formatted_phone_number", "formatted_address", "address_component"],
        )
        detail_result = detail.get("result", {})

        website = detail_result.get("website")
        if not website:
            return None
        if exclude_domains:
            from urllib.parse import urlparse
            domain = urlparse(website).hostname or ""
            if any(d in domain for d in exclude_domains):
                return None

        rating = place.get("rating")
        if min_rating is not None and (rating is None or rating < min_rating):
            return None

        address_components = detail_result.get("address_component", [])

        return {
            "name": place.get("name", ""),
            "website": website,
            "phone": detail_result.get("formatted_phone_number", ""),
            "address": detail_result.get("formatted_address", ""),
            "rating": rating,
            "category": self._map_category(place.get("types", [])),
            "city": self._extract_city(address_components),
            "country": self._extract_country(address_components),
            "place_id": place["place_id"],
        }

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
