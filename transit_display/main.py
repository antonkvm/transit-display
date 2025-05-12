import datetime
import logging
import threading
import time

import transit_display.gui as gui
from transit_display.trip_fetcher import Departure, fetch_departures_for_all_stations_concurrently
from transit_display.weather_fetcher import WeatherData, fetch_weather_until_success

logger = logging.getLogger(__name__)


def clock_loop(event: threading.Event):
    previous_minute = -1
    while True:
        new_minute = datetime.datetime.now().minute
        clock_changed = new_minute != previous_minute
        if clock_changed:
            event.set()
        previous_minute = new_minute
        time.sleep(1)


def trip_fetch_loop(departures: list[Departure], dep_lock: threading.Lock, event: threading.Event):
    """Continuously updates the `departures` list reference in-place every 15 seconds and within the thread lock."""
    while True:
        new_departures = fetch_departures_for_all_stations_concurrently()

        with dep_lock:
            if len(new_departures) != 0 and new_departures != departures:
                # update the list in-place:
                departures.clear()
                departures.extend(new_departures)

                event.set()

        time.sleep(15)


def weather_fetch_loop(shared_weather: dict[str, WeatherData], lock: threading.Lock, event: threading.Event):
    """Continuously fetches and updates weather data at full quarter-hour intervals based on server timestamps."""
    interval_minutes = 15
    offset_minutes = 1  # give server a minute to update its data before fetching

    while True:
        weather = fetch_weather_until_success()

        with lock:
            shared_weather["data"] = weather

        event.set()

        last_server_update = weather.timestamp
        next_fetch_time = last_server_update + datetime.timedelta(minutes=interval_minutes + offset_minutes)
        now = datetime.datetime.now()
        sleep_seconds = (next_fetch_time - now).total_seconds()

        if sleep_seconds <= 0:
            logger.warning(
                f"Cosmic event: weather server returned data with future timestamp: {weather.timestamp}. "
                f"Scheduling next fetch for {(now + datetime.timedelta(minutes=15))} (15 minutes from now)."
            )
            time.sleep(60 * 15)
            continue

        logger.info(f"Scheduled next weather fetch for {next_fetch_time}. Sleeping for {sleep_seconds} seconds.")
        time.sleep(sleep_seconds)


def gui_loop():
    update_event = threading.Event()
    update_event.set()  # initialize flag as True to allow first GUI render

    departures = []
    dep_lock = threading.Lock()
    weather = {"data": None}  # dicts allow in-place mutation of values from threads and avoids local rebinding
    weather_lock = threading.Lock()

    threading.Thread(target=trip_fetch_loop, args=[departures, dep_lock, update_event], daemon=True).start()
    threading.Thread(target=clock_loop, args=[update_event], daemon=True).start()
    threading.Thread(target=weather_fetch_loop, args=[weather, weather_lock, update_event], daemon=True).start()

    while True:
        update_event.wait(timeout=15.0)

        # immediately clear event flag, so updates triggered during render are 'queued' for the next loop:
        update_event.clear()

        # only need a shallow copie bc underlying data is immutable (frozen dataclass)
        with dep_lock:
            departures_copy = departures.copy()
        with weather_lock:
            weather_copy = weather["data"]

        screen_img = gui.draw_gui(departures_copy, weather_copy)
        gui.write_rgb_to_frame_buffer(screen_img)


def run():
    if not gui.FRAMEBUFFER.exists():
        logger.info(f"No framebuffer {gui.FRAMEBUFFER} detected, showing snapshot in viewer")
        gui.show_gui_snapshot_window()
    else:
        logger.info(f"Framebuffer {gui.FRAMEBUFFER} found, Starting GUI loop")
        try:
            gui_loop()
        except Exception as e:
            logger.exception("GUI loop failed.")
            gui.death_screen(str(e))
            raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger.info("Starting GUI as a module")
    run()
