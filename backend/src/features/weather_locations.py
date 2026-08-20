"""Tournament city coordinates for weather lookup."""
from __future__ import annotations

TOURNAMENT_COORDS: dict[str, tuple[float, float]] = {
    "Melbourne": (-37.81, 144.96),
    "Sydney": (-33.87, 151.21),
    "Brisbane": (-27.47, 153.03),
    "Adelaide": (-34.93, 138.60),
    "Auckland": (-36.85, 174.76),
    "Indian Wells": (33.72, -116.31),
    "Miami": (25.78, -80.22),
    "Cincinnati": (39.10, -84.51),
    "Washington": (38.90, -77.04),
    "Atlanta": (33.75, -84.39),
    "Dallas": (32.78, -96.80),
    "Houston": (29.76, -95.37),
    "Winston": (36.10, -80.27),
    "Paris": (48.86, 2.35),
    "Roland Garros": (48.84, 2.25),
    "French Open": (48.84, 2.25),
    "Marseille": (43.30, 5.37),
    "Lyon": (45.76, 4.84),
    "Montpellier": (43.61, 3.88),
    "Metz": (49.12, 6.18),
    "Wimbledon": (51.42, -0.22),
    "Queen": (51.49, -0.19),
    "Eastbourne": (50.77, 0.28),
    "Rome": (41.90, 12.50),
    "Madrid": (40.42, -3.70),
    "Barcelona": (41.39, 2.17),
    "Mallorca": (39.57, 2.65),
    "Monte Carlo": (43.74, 7.43),
    "Hamburg": (53.55, 10.00),
    "Stuttgart": (48.78, 9.18),
    "Halle": (52.06, 8.36),
    "Queen's Club": (51.49, -0.19),
    "s-Hertogenbosch": (51.69, 5.30),
    "Berlin": (52.52, 13.40),
    "Munich": (48.14, 11.58),
    "Vienna": (48.21, 16.37),
    "Basel": (47.56, 7.59),
    "Stockholm": (59.33, 18.07),
    "St. Petersburg": (59.93, 30.32),
    "Moscow": (55.76, 37.62),
    "Dubai": (25.27, 55.30),
    "Doha": (25.29, 51.53),
    "Beijing": (39.90, 116.40),
    "Shanghai": (31.23, 121.47),
    "Tokyo": (35.68, 139.69),
    "Chengdu": (30.57, 104.07),
    "Zhuhai": (22.27, 113.57),
    "Hong Kong": (22.30, 114.17),
    "Seoul": (37.57, 126.98),
    "Buenos Aires": (-34.61, -58.38),
    "Rio de Janeiro": (-22.91, -43.17),
    "Sao Paulo": (-23.55, -46.63),
    "Bogota": (4.71, -74.07),
    "Quito": (-0.18, -78.47),
    "Mexico City": (19.43, -99.13),
    "Acapulco": (16.86, -99.88),
    "Toronto": (43.65, -79.38),
    "Montreal": (45.50, -73.57),
    "Johannesburg": (-26.20, 28.05),
    "Cape Town": (-33.92, 18.42),
    "Antwerp": (51.22, 4.40),
    "Rotterdam": (51.92, 4.48),
    "Sofia": (42.70, 23.32),
    "Pune": (18.52, 73.86),
}


def get_coords(tourney_name: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a tournament by fuzzy name match."""
    if not isinstance(tourney_name, str):
        return None
    t_lower = tourney_name.lower()
    for key, coords in TOURNAMENT_COORDS.items():
        if key.lower() in t_lower:
            return coords
    return None