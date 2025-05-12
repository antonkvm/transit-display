import logging
import time
from dataclasses import dataclass, fields
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeatherData:
    timestamp: datetime
    temperature: float
    uv_index: float
    temperature_daily_min: float
    temperature_daily_max: float
    uv_index_daily_max: float


#? put coordinates in yaml?
def get_weather() -> WeatherData:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 52.51356805426098,
        "longitude": 13.32652568167527,
        "timezone": "Europe/Berlin",
        "current": ["temperature_2m", "uv_index"],
        "daily": ["temperature_2m_min", "temperature_2m_max", "uv_index_max"],
        "forecast_days": 1,
    }

    r = requests.get(url, params)
    r.raise_for_status()
    data = r.json()

    logger.info("Successfully fetched new weather data")
    
    return WeatherData(
        datetime.fromisoformat(data['current']['time']),
        round(data['current']['temperature_2m'], 1),
        round(data['current']['uv_index'], 1),
        round(data['daily']['temperature_2m_min'][0], 1),
        round(data['daily']['temperature_2m_max'][0], 1),
        round(data['daily']['uv_index_max'][0], 1)
    )
    
def fetch_weather_until_success():
    retry_delay_seconds = 15
    while True:
        try:
            return get_weather()
        except (ValueError, requests.RequestException) as e:
            logger.warning(f"Weather fetch failed, retrying in {retry_delay_seconds}. Error: {e}")
            time.sleep(retry_delay_seconds)


if __name__ == "__main__":
    weather = get_weather()
    for field in fields(weather):
        print(field.name, getattr(weather, field.name), sep=": ")
