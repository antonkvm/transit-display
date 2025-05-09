import logging
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml
from tabulate import tabulate

logger = logging.getLogger(__name__)

API_BASE = "https://v6.bvg.transport.rest"


DEFAULT_STATIONS = [{"name": "Zoologischer Garten", "stationID": 900023201, "fetch_products": ["bus"]}]


PRODUCTS = ["suburban", "subway", "tram", "bus", "ferry", "express", "regional"]


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


def time_only(iso_timestamp: str):
    dt = datetime.fromisoformat(iso_timestamp)
    return dt.strftime("%H:%M")


class Departure:
    def __init__(self, departure_json: dict):
        self.trip_id: str = departure_json["tripId"]
        self.line: str = departure_json["line"]["name"]
        self.destination: str = departure_json["destination"]["name"]
        self.when: str = departure_json["when"]
        self.delay_seconds: int | None = departure_json["delay"]
        self.remarks: list[dict] = departure_json["remarks"]
        self.product: str = departure_json["line"]["product"]
        self.process_attributes()

    def process_attributes(self):
        if self.line == "S41":
            self.destination = "⟳ " + self.destination
        elif self.line == "S42":
            self.destination = "⟲ " + self.destination
        self.destination = self.destination.replace("(Berlin)", "").strip()
        self.when = time_only(self.when)
        self.delay_minutes = self.delay_seconds // 60 if self.delay_seconds else 0
        self.delay_minutes_str = self.prettify_delay_minutes()
        if self.remarks:
            self.remarks = [remark["summary"] for remark in self.remarks if remark["type"] == "warning"]
        self.remarks = " -- ".join(self.remarks)

    def prettify_delay_minutes(self) -> str:
        delay = self.delay_minutes
        if delay == 0:
            return ""
        if delay > 0:
            return f"+{delay}"
        return f"{delay}"

    def __str__(self):
        s = f"{self.line} | {self.destination} | {self.when} "
        if self.delay_minutes:
            s += f"(+{self.delay_minutes})" if self.delay_minutes > 0 else f"({self.delay_minutes})"
        if self.remarks:
            s += f" ({self.remarks})"
        return s

    def __hash__(self):
        hash_src = (self.line, self.when, self.delay_seconds, self.product, self.remarks)
        return hash(hash_src)

    def __eq__(self, value):
        if isinstance(value, Departure):
            me = (self.line, self.when, self.delay_seconds, self.product, self.remarks)
            other = (value.line, value.when, value.delay_seconds, value.product, value.remarks)
            return me == other
        else:
            return NotImplemented


def drop_duplicate_departures(departures: list[Departure]) -> list[Departure]:
    return list(set(departures))


def make_table(departures: list[Departure]) -> str:
    headers = ["Line", "Destination", "Arrival", "Delay", "Remark", "TripID", "Hash"]
    data = [[d.line, d.destination, d.when, d.delay_minutes, d.remarks, d.trip_id, d.__hash__()] for d in departures]
    table = tabulate(data, headers)
    return table


def fetch_departures() -> list[Departure] | None:
    next_departures: list[Departure] = []

    try:
        stations = load_stations_from_config()
    except Exception:
        logger.warning("No stations from config yaml available, using default stations.")
        stations = DEFAULT_STATIONS

    for station in stations:
        station_name = station["name"]
        station_id = station["stationID"]
        desired_products = station["fetch_products"]

        request_params = {
            "when": "now",
            "duration": 600,
            "results": 12,
            "linesOfStops": False,
            "remarks": True,
            "language": "de",
        }
        product_params = {k: True if k in desired_products else False for k in PRODUCTS}
        request_params.update(product_params)

        r = requests.get(url=f"{API_BASE}/stops/{station_id}/departures", params=request_params)

        if not r.ok:
            msg = f"HTTP error {r.status_code}: Failed to fetch stop {station_name}. Reason: {r.reason}"
            logger.error(msg)
            continue
        departures_here: list[dict] = [d for d in r.json()["departures"]]

        for departure_json in departures_here:
            if "cancelled" in departure_json.keys():
                continue
            departure = Departure(departure_json)
            next_departures.append(departure)

    next_departures = drop_duplicate_departures(next_departures)  # maybe obsolete
    next_departures.sort(key=lambda d: d.when)

    if not next_departures:
        return None
    return next_departures


def fetch_departures_keep_trying(interval: int = 10) -> list[Departure]:
    """Fetch departures. If none are returned from the server, keep trying every 10 seconds."""
    departures = fetch_departures()
    while not departures:
        departures = fetch_departures()
        time.sleep(interval)
    return departures


if __name__ == "__main__":
    departures = fetch_departures()
    print(make_table(departures))
