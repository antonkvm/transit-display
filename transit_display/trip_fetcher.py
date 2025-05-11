import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
import yaml
from tabulate import tabulate

logger = logging.getLogger(__name__)


API_BASE = "https://v6.bvg.transport.rest"
DEFAULT_STATIONS = [{"name": "Zoologischer Garten", "stationID": 900023201, "fetch_products": ["bus"]}]
PRODUCTS = ["suburban", "subway", "tram", "bus", "ferry", "express", "regional"]

FETCH_RETRY_TIMEOUT = 10.0


@dataclass(frozen=True)
class Departure:
    trip_id: str
    line: str
    destination: str
    when: str
    delay_seconds: int
    delay_minutes: int
    delay_minutes_str: str
    product: str

    @classmethod
    def from_json(cls, json: dict) -> "Departure":
        trip_id: str = json["tripId"]
        line: str = json["line"]["name"]
        destination: str = json["destination"]["name"]
        when: str = json["when"]
        delay_seconds: int = json.get("delay") or 0
        product: str = json["line"]["product"]

        if line == "S41":
            destination = "⟳ " + destination
        elif line == "S42":
            destination = "⟲ " + destination

        destination = destination.replace("(Berlin)", "").strip()

        when = datetime.fromisoformat(when).strftime("%H:%M")

        delay_minutes: int = delay_seconds // 60 if delay_seconds else 0
        if delay_minutes == 0:
            delay_minutes_str = ""
        elif delay_minutes > 0:
            delay_minutes_str = f"+{delay_minutes}"
        else:
            delay_minutes_str = str(delay_minutes)

        return cls(trip_id, line, destination, when, delay_seconds, delay_minutes, delay_minutes_str, product)

    def __hash__(self):
        """Note: Exclude tripId from hash function bc BVG may assign different tripIds to physically identical trips."""
        hash_src = (self.line, self.when, self.delay_seconds, self.product)
        return hash(hash_src)

    def __eq__(self, value):
        """Note: Decide equality without tripId bc BVG may assign different tripIds to physically identical trips."""
        if not isinstance(value, Departure):
            return NotImplemented
        me = (self.line, self.when, self.delay_seconds, self.product)
        you = (value.line, value.when, value.delay_seconds, value.product)
        return me == you


def load_stations_from_config() -> list[dict]:
    """Loads stations from config yaml and returns them as `list[dict]`. If load fails, returns `DEFAULT_STATIONS`."""
    config_file = Path(__file__).parent.parent / "stations.yaml"
    try:
        with config_file.open("r", encoding="utf-8") as f:
            stations = yaml.safe_load(f)
        return stations["stations"]
    except Exception as e:
        logger.error(f"Failed to load config yaml. Loading default station Zoologischer Garten. Error: {e}")
        return DEFAULT_STATIONS


def drop_duplicate_departures(departures: list[Departure]) -> list[Departure]:
    return list(set(departures))


def make_table(departures: list[Departure]) -> str:
    headers = ["Line", "Destination", "Arrival", "Delay", "TripID", "Hash"]
    data = [[d.line, d.destination, d.when, d.delay_minutes, d.trip_id, d.__hash__()] for d in departures]
    table = tabulate(data, headers)
    return table


def fetch_departures(station: dict) -> list[Departure]:
    """Fetch departures for a given station.

    Args:
        station (dict): A dict with keys `name`, `stationID`, `fetch_products`. `fetch_products` should be a list of desired fetch products (e.g `['bus', 'suburban']`).

    Raises:
        ValueError: The server responded with a list of departures but the list is empty.
        requests.RequestException: Raised by the requests module for ambiguous error while handling your request.

    Returns:
        list[Departure]: A list of containing the departures from that station, with the desired products.
    """
    station_name = station["name"]
    station_id = station["stationID"]
    desired_products = station["fetch_products"]
    product_params = {k: True if k in desired_products else False for k in PRODUCTS}

    request_params = {
        "when": "now",
        "duration": 600,
        "results": 12,
        "linesOfStops": False,
        "remarks": True,
        "language": "de",
        **product_params,
    }

    r = requests.get(f"{API_BASE}/stops/{station_id}/departures", request_params)
    r.raise_for_status()

    departure_dicts: list[dict] = r.json()["departures"]
    departures = [Departure.from_json(d) for d in departure_dicts if d.get("cancelled") is not True]

    departures = drop_duplicate_departures(departures)
    departures = sorted(departures, key=lambda d: d.when)  # string comparison but still somehow works

    if not departures:
        raise ValueError(f"{station_name}: Received empty departures list")

    return departures


def fetch_departures_retry_until_success(station: dict) -> list[Departure]:
    """Wrapper function that calls `fetch_departures` until the server responds with something useful."""
    while True:
        try:
            return fetch_departures(station)
        except (ValueError, requests.RequestException) as e:
            logger.warning(f"{station['name']}: Fetch failed, retrying in {FETCH_RETRY_TIMEOUT} seconds. Error: {e}")
            time.sleep(FETCH_RETRY_TIMEOUT)


def fetch_departures_for_all_stations_concurrently() -> list[Departure]:
    """Fetch departures for the stations in the config yaml concurrently. Uses one fetch thread per station.

    Raises:
        Exception: Any unhandled exception emitted by a fetch thread.

    Returns:
        list[Departure]: A time-sorted list of the fetched departures for all stations.
    """
    station_dicts = load_stations_from_config()

    departures: list[Departure] = []

    with ThreadPoolExecutor(max_workers=len(station_dicts)) as executor:
        futures_to_station_map = {
            executor.submit(fetch_departures_retry_until_success, station): station["name"] for station in station_dicts
        }

        for future in as_completed(futures_to_station_map):
            station_name = futures_to_station_map[future]
            try:
                result = future.result()
                departures.extend(result)
                logger.info(f"Successfully fetched new trips for {station_name}")
            except Exception:
                logger.exception(f"Unexpected fatal error during concurrent fetch of {station_name}")
                raise

    departures = sorted(departures, key=lambda dep: dep.when)  # string comparison but still somehow works
    return departures


if __name__ == "__main__":
    departures = fetch_departures_for_all_stations_concurrently()
    print(make_table(departures))
