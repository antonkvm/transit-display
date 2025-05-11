import datetime
import logging
import threading
import time

import transit_display.gui as gui
from transit_display.trip_fetcher import Departure, fetch_departures_for_all_stations_concurrently

logger = logging.getLogger(__name__)

FETCH_INTERVAL_SEC = 15


def clock_loop(event: threading.Event):
    previous_minute = -1
    while True:
        new_minute = datetime.datetime.now().minute
        clock_changed = new_minute != previous_minute
        if clock_changed:
            event.set()
        previous_minute = new_minute


def trip_fetch_loop(departures: list[Departure], dep_lock: threading.Lock, event: threading.Event):
    """Continuously updates the `departures` list reference in-place at an interval and within the thread lock."""
    while True:
        new_departures = fetch_departures_for_all_stations_concurrently()

        with dep_lock:
            if len(new_departures) != 0 and new_departures != departures:
                # update the list in-place:
                departures.clear()
                departures.extend(new_departures)

                event.set()

        time.sleep(FETCH_INTERVAL_SEC)


def gui_loop():
    update_event = threading.Event()
    update_event.set()  # initialize flag as True to allow first GUI render

    departures = []
    dep_lock = threading.Lock()
    fetch_thread = threading.Thread(target=trip_fetch_loop, args=[departures, dep_lock, update_event], daemon=True)
    fetch_thread.start()

    clock_thread = threading.Thread(target=clock_loop, args=[update_event])
    clock_thread.start()

    while True:
        update_event.wait(timeout=15.0)

        # immediately clear event flag, so updates triggered during render are 'queued' for the next loop:
        update_event.clear()

        # only need a shallow copy bc the Departure objects in the list are immutable (frozen dataclass)
        with dep_lock:
            departures_copy = departures.copy()

        screen_img = gui.draw_gui(departures_copy)
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