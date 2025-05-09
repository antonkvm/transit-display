import datetime
import logging
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from transit_display.trip_fetcher import Departure, fetch_departures_keep_trying

logger = logging.getLogger(__name__)

NUM_ROWS, ROW_HEIGHT = 18, 40  # these need to multiply to 720
COL_WIDTHS = [80, 540, 100]  # these need to add up to 720
FRAMEBUFFER = Path("/dev/fb0")

FONT_STYLE = "./assets/DejaVuSans.ttf"

SBAHN_GREEN = (64, 131, 53)
METROBUS_YELLOW = (233, 208, 33)
BUS_PURPLE = (160, 1, 121)
LATE_RED = (255, 0, 0)
EARLY_YELLOW = (255, 255, 0)


def draw_line_info(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    # subtract 1 pixel from the bottom right boundary bc pixel indices start at 0
    padding = 5
    bg_bbox_topleft = (x + padding, y + padding)
    bg_bbox_bottomright = (x + col_width - 1 - padding, y + ROW_HEIGHT - 1 - padding)
    bg_bbox = [bg_bbox_topleft, bg_bbox_bottomright]

    if departure.product == "suburban":
        bg_color = SBAHN_GREEN
        text_color = "white"
    elif departure.product == "bus" and departure.line.startswith("M"):
        bg_color = METROBUS_YELLOW
        text_color = "black"
    elif departure.product == "bus":
        bg_color = BUS_PURPLE
        text_color = "white"
    else:
        bg_color = "grey"
        text_color = "white"

    draw.rounded_rectangle(bg_bbox, 7, bg_color)

    # for easy centering, set text anchor to vertical and horizontal middle of text
    text_anchor = "mm"

    # set (x,y) of text anchor to absolute center of cell
    # manually adjust coordinates for best visual result, as there is no pixel-perfect center for even dimensions
    text_x = get_horizontal_center(x, col_width) + 1
    text_y = get_vertical_center(y, ROW_HEIGHT) + 1

    font = ImageFont.truetype(FONT_STYLE, 30)
    draw.text((text_x, text_y), departure.line, text_color, font, text_anchor)


def truncate_text(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_width: int) -> str:
    if draw.textlength(text, font) <= max_width:
        return text
    while draw.textlength(text + "...", font) > max_width:
        text = text[:-1]
    return text + "..."


def get_horizontal_center(x: int, width: int):
    return x + width // 2


def get_vertical_center(y: int, height: int) -> int:
    return y + height // 2


def draw_destination(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    text = departure.destination

    text_anchor = "lm"  # left-middle
    text_x = x + 5
    text_y = get_vertical_center(y, ROW_HEIGHT)

    font = ImageFont.truetype(FONT_STYLE, 30)
    text = truncate_text(text, font, draw, col_width)

    draw.text((text_x, text_y), text, "white", font, text_anchor)


def draw_depart_time(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    text = departure.when
    delay_int = departure.delay_minutes

    if delay_int > 0:
        text_color = LATE_RED
    elif delay_int < 0:
        text_color = EARLY_YELLOW
    else:
        text_color = "white"

    text_anchor = "mm"  # middle-middle
    text_x = get_horizontal_center(x, col_width)
    text_y = get_vertical_center(y, ROW_HEIGHT)

    font = ImageFont.truetype(FONT_STYLE, 30)
    draw.text((text_x, text_y), text, text_color, font, text_anchor)


def draw_date_time(draw: ImageDraw.ImageDraw):
    now = datetime.datetime.now()
    # date_str = now.strftime("%a, %d. %b %Y")
    time_str = now.strftime("%H:%M")

    text_anchor = "mm"
    x = 360
    y = get_vertical_center(y=0, height=ROW_HEIGHT * 2)

    font = ImageFont.truetype(FONT_STYLE, 80)
    draw.text((x, y), time_str, "white", font, text_anchor)


def draw_gui(departures: list[Departure]) -> Image.Image:
    image = Image.new("RGB", (720, 720), "black")
    draw = ImageDraw.Draw(image)

    draw_date_time(draw)

    for row in range(NUM_ROWS):
        # leave space at top to display time and date
        y = (row + 2) * ROW_HEIGHT

        try:
            departure = departures[row]
        except IndexError:
            # more rows than available departures, leave remaining rows empty
            break

        for col, col_width in enumerate(COL_WIDTHS):
            x = sum(COL_WIDTHS[:col])

            # grid outline for testing:
            # draw.rectangle([(x, y), (x + col_width - 1, y + ROW_HEIGHT - 1)], outline="red")

            if col == 0:
                draw_line_info(departure, draw, x, y, col_width)
            elif col == 1:
                draw_destination(departure, draw, x, y, col_width)
            elif col == 2:
                draw_depart_time(departure, draw, x, y, col_width)

    return image


def write_rgb_to_frame_buffer(rgb_image: Image.Image):
    arr_rgb = np.array(rgb_image)

    # reverse color channel order:
    arr_bgr = arr_rgb[:, :, ::-1]

    # add alpha channel bc pimoroni display wants that
    alpha = np.zeros((720, 720, 1), dtype=np.uint8)
    arr_bgra = np.concatenate((arr_bgr, alpha), axis=2)

    with Path(FRAMEBUFFER).open("wb") as fb:
        fb.write(arr_bgra.tobytes())


def show_gui_snapshot_window():
    departures = fetch_departures_keep_trying()
    img = draw_gui(departures)
    img.show()


# todo: fetching departures blocks clock update
# todo: when one station cannot be fetched, it disappears from screen, bc the list is different. Solve with caching?
# --> easier: just add condition that the new list must be non-empty
def run_gui_loop():
    departures = fetch_departures_keep_trying()
    last_fetch = time.time()
    while True:
        now = time.time()
        if now - last_fetch > 10:
            new_departures = fetch_departures_keep_trying()
            if new_departures != departures:
                departures = new_departures
        screen = draw_gui(departures)
        write_rgb_to_frame_buffer(screen)
        time.sleep(1)


def death_screen():
    text = "I died :("
    screen = Image.new("RGB", (720, 720), "black")
    draw = ImageDraw.Draw(screen)
    text_anchor = "mm"
    font = ImageFont.truetype(FONT_STYLE, 50)
    draw.text((360, 360), text, "red", font, text_anchor)
    write_rgb_to_frame_buffer(screen)


def run():
    if not FRAMEBUFFER.exists():
        logger.info(f"No framebuffer {FRAMEBUFFER} detected, showing snapshot in viewer")
        show_gui_snapshot_window()
    else:
        logger.info("Starting GUI loop")
        run_gui_loop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger.info("Starting GUI as a module")
    try:
        run()
    except BaseException as e:
        logger.error(f"GUI loop was interrupted. Error: {e}")
        death_screen()
