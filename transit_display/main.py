import datetime
import logging
import threading
import time

import transit_display.gui as gui
from transit_display.trip_fetcher import trip_fetch_loop
from transit_display.weather_fetcher import weather_fetch_loop
from transit_display.wifi_checker import wifi_check_loop

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


def main_loop():
    update_event = threading.Event()
    update_event.set()  # initialize flag as True to allow first GUI render

    departures = []
    dep_lock = threading.Lock()
    weather = {"data": None}  # dicts allow in-place mutation of values from threads and avoids local rebinding
    weather_lock = threading.Lock()

    threading.Thread(
        target=trip_fetch_loop, name="TripFetchThread", args=[departures, dep_lock, update_event], daemon=True
    ).start()
    threading.Thread(target=clock_loop, name="ClockThread", args=[update_event], daemon=True).start()
    threading.Thread(
        target=weather_fetch_loop, name="WeatherThread", args=[weather, weather_lock, update_event], daemon=True
    ).start()
    threading.Thread(target=wifi_check_loop, name="WifiCheckThread", daemon=True).start()

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
            main_loop()
        except Exception as e:
            logger.exception("GUI loop failed.")
            gui.death_screen(str(e))
            raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        # format="%(asctime)s - %(levelname)s - %(threadName)s - %(message)s",
        format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Starting GUI as a module")
    run()
