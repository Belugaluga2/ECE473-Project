"""Canonical study locations shared by every module. Do not rename keys; other modules import them.

Each PRF study site pairs a Kalshi monthly-rain settlement station (NWS climate site, the
"CLIxxx" code in Kalshi's rules text) with a PRF-heavy county nearby. Two PRF grids are studied
per site: the grid containing the settlement station (isolates station-vs-gridded-data
measurement mismatch) and the grid containing the farm point (adds geographic basis risk).

Sources:
- Station coordinates and IDs: ACIS StnMeta (data.rcc-acis.org), retrieved 2026-10-29.
- Farm points: US Census 2024 Gazetteer county internal points (INTPTLAT/INTPTLONG).
- Kalshi series and CLI codes: Kalshi public API market rules_primary text, retrieved 2026-10-29.

Station record caveats: DEN (Denver Intl) starts 1994-07 and DFW starts 1974-01 as single
stations; ACIS "threaded" records (e.g. sid "DENthr") extend them back with predecessor sites.
"""
from math import asin, cos, radians, sin, sqrt

STUDY_SITES = {
    "DFW": {"kalshi_series": "KXRAINDALM", "cli_code": "CLIDFW", "city": "Dallas-Fort Worth, TX",
             "station_name": "DAL-FTW WSCMO AP", "icao": "KDFW", "ghcn": "USW00003927", "wban": "03927",
             "station_lat": 32.89744, "station_lon": -97.02196,
             "farm_county": "Parker County, TX", "farm_fips": "48367",
             "farm_lat": 32.777096, "farm_lon": -97.805905,
             "land_use": "hay + grazing (Cross Timbers)"},
    "SAT": {"kalshi_series": "KXRAINSATXM", "cli_code": "CLISAT", "city": "San Antonio, TX",
             "station_name": "SAN ANTONIO INTL AP", "icao": "KSAT", "ghcn": "USW00012921", "wban": "12921",
             "station_lat": 29.54429, "station_lon": -98.48395,
             "farm_county": "Atascosa County, TX", "farm_fips": "48013",
             "farm_lat": 28.891478, "farm_lon": -98.535381,
             "land_use": "rangeland grazing (South Texas Plains)"},
    "OKC": {"kalshi_series": "KXRAINOKCM", "cli_code": "CLIOKC", "city": "Oklahoma City, OK",
             "station_name": "OKLAHOMA CITY WILL ROGERS WORLD AP", "icao": "KOKC", "ghcn": "USW00013967", "wban": "13967",
             "station_lat": 35.38843, "station_lon": -97.60035,
             "farm_county": "Grady County, OK", "farm_fips": "40051",
             "farm_lat": 35.021058, "farm_lon": -97.88689,
             "land_use": "pasture/rangeland + hay"},
    "SGF": {"kalshi_series": "KXRAINSGFM", "cli_code": "CLISGF", "city": "Springfield, MO",
             "station_name": "SPRINGFIELD WSO AP", "icao": "KSGF", "ghcn": "USW00013995", "wban": "13995",
             "station_lat": 37.23983, "station_lon": -93.38995,
             "farm_county": "Dade County, MO", "farm_fips": "29057",
             "farm_lat": 37.43235, "farm_lon": -93.854878,
             "land_use": "hay (tall fescue) + pasture"},
    "DEN": {"kalshi_series": "KXRAINDENM", "cli_code": "CLIDEN", "city": "Denver, CO",
             "station_name": "DENVER INTL AP", "icao": "KDEN", "ghcn": "USW00003017", "wban": "03017",
             "station_lat": 39.84657, "station_lon": -104.65623,
             "farm_county": "Elbert County, CO", "farm_fips": "08039",
             "farm_lat": 39.315157, "farm_lon": -104.114076,
             "land_use": "shortgrass rangeland grazing"},
    "ABQ": {"kalshi_series": "KXRAINABQM", "cli_code": "CLIABQ", "city": "Albuquerque, NM",
             "station_name": "ALBUQUERQUE INTL AP", "icao": "KABQ", "ghcn": "USW00023050", "wban": "23050",
             "station_lat": 35.04189, "station_lon": -106.61545,
             "farm_county": "Torrance County, NM", "farm_fips": "35057",
             "farm_lat": 34.554998, "farm_lon": -105.890577,
             "land_use": "arid rangeland grazing"},
    "TPA": {"kalshi_series": "KXRAINTPAM", "cli_code": "CLITPA", "city": "Tampa, FL",
             "station_name": "TAMPA INTL AP", "icao": "KTPA", "ghcn": "USW00012842", "wban": "12842",
             "station_lat": 27.96331, "station_lon": -82.54,
             "farm_county": "Hardee County, FL", "farm_fips": "12049",
             "farm_lat": 27.492846, "farm_lon": -81.82158,
             "land_use": "improved pasture (bahiagrass)"},
}

# Row-crop contrast site. PRF does not insure row crops; used for crop-sensitivity context only.
CONTRAST_SITES = {
    "ORD": {"kalshi_series": "KXRAINCHIM", "cli_code": "CLIORD", "city": "Chicago, IL",
             "station_name": "CHICAGO OHARE INTL AP", "icao": "KORD", "ghcn": "USW00094846", "wban": "94846",
             "station_lat": 41.96017, "station_lon": -87.93164,
             "farm_county": "Kane County, IL", "farm_fips": "17089",
             "farm_lat": 41.939594, "farm_lon": -88.42804,
             "land_use": "corn/soybean"},
}

ALL_SITES = {**STUDY_SITES, **CONTRAST_SITES}


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in statute miles."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 3958.8 * asin(sqrt(a))


def station_farm_distance_miles(site_key):
    s = ALL_SITES[site_key]
    return haversine_miles(s["station_lat"], s["station_lon"], s["farm_lat"], s["farm_lon"])


if __name__ == "__main__":
    for k in ALL_SITES:
        print(f"{k}: station-to-farm {station_farm_distance_miles(k):.1f} mi")
