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
