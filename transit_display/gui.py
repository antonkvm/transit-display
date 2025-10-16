import logging
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from transit_display.trip_fetcher import Departure, fetch_departures_for_all_stations_concurrently
from transit_display.weather_fetcher import WeatherData, get_weather

logger = logging.getLogger(__name__)

NUM_ROWS, ROW_HEIGHT = 18, 40  # these need to multiply to 720
COL_WIDTHS = [80, 540, 100]  # these need to add up to 720
FRAMEBUFFER = Path("/dev/fb0")

FONT_STYLE = str(Path(__file__).absolute().parent / "assets/DejaVuSans.ttf")
FONT_STYLE_BOLD = str(Path(__file__).absolute().parent / "assets/DejaVuSansCondensed-Bold.ttf")

FONT_20 = ImageFont.truetype(FONT_STYLE, 20)
FONT_30 = ImageFont.truetype(FONT_STYLE, 30)
FONT_50 = ImageFont.truetype(FONT_STYLE, 50)
FONT_80 = ImageFont.truetype(FONT_STYLE, 80)
FONT_20_BOLD = ImageFont.truetype(FONT_STYLE_BOLD, 20)
FONT_30_BOLD = ImageFont.truetype(FONT_STYLE_BOLD, 30)
FONT_50_BOLD = ImageFont.truetype(FONT_STYLE_BOLD, 50)
FONT_80_BOLD = ImageFont.truetype(FONT_STYLE_BOLD, 80)

SBAHN_GREEN = (0, 119, 52)
METROBUS_YELLOW = (233, 208, 33)
BUS_PURPLE = (160, 1, 121)
LATE_RED = (255, 0, 0)
EARLY_YELLOW = (255, 255, 0)


def draw_line_info(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    # subtract 1 pixel from the bottom right boundary bc pixel indices start at 0
    padding = 3
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

    draw.rounded_rectangle(bg_bbox, 15, bg_color)

    # for easy centering, set text anchor to vertical and horizontal middle of text
    text_anchor = "mm"

    # set (x,y) of text anchor to absolute center of cell
    # manually adjust coordinates for best visual result, as there is no pixel-perfect center for even dimensions
    text_x = get_horizontal_center(x, col_width) + 1
    text_y = get_vertical_center(y, ROW_HEIGHT) + 1

    draw.text((text_x, text_y), departure.line, text_color, FONT_30_BOLD, text_anchor)


def truncate_text(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> str:
    if draw.textlength(text, font) <= max_width:
        return text
    while draw.textlength(text + "...", font) > max_width:
        text = text[:-1]
    return text + "..."


def get_horizontal_center(left_x: int, box_width: int):
    return left_x + box_width // 2


def get_vertical_center(top_y: int, box_height: int) -> int:
    return top_y + box_height // 2


def draw_destination(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    text = departure.destination

    text_anchor = "lm"  # left-middle
    padding_left = 10
    text_x = x + padding_left
    text_y = get_vertical_center(y, ROW_HEIGHT)

    text = truncate_text(text, FONT_30, draw, col_width - padding_left)

    draw.text((text_x, text_y), text, "white", FONT_30, text_anchor)


def draw_depart_time(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    text = datetime.strftime(departure.when, "%H:%M")
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

    draw.text((text_x, text_y), text, text_color, FONT_30_BOLD, text_anchor)


def draw_trip_list(draw: ImageDraw.ImageDraw, departures: list[Departure]):
    # leave 2 rows at the top for clock an weather:
    for row in range(2, NUM_ROWS):
        y = row * ROW_HEIGHT

        if row % 2 == 0:
            draw.rectangle(((0, y), (720, y + ROW_HEIGHT)), (25, 25, 25))

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


def draw_clock(draw: ImageDraw.ImageDraw):
    now = datetime.now()
    # date_str = now.strftime("%a, %d. %b %Y")
    time_str = now.strftime("%H:%M")

    text_anchor = "mm"
    box_height = ROW_HEIGHT * 2
    x = 360
    y = get_vertical_center(top_y=0, box_height=box_height)

    draw.text((x, y), time_str, "white", FONT_80, text_anchor)


def draw_weather_info(draw: ImageDraw.ImageDraw, weather: WeatherData | None):
    if weather:
        draw_temperature_info(draw, weather)
        draw_uv_info(draw, weather)
    else:
        logger.warning("No weather data available to draw, leaving area blank")


def draw_temperature_info(draw: ImageDraw.ImageDraw, weather: WeatherData):
    temp = f"{weather.temperature}°"
    min_max = f"\u2191{weather.temperature_daily_max}° \u2193{weather.temperature_daily_min}°"

    margin_left = 10
    main_xy = (0 + margin_left, get_vertical_center(0, ROW_HEIGHT))
    subt_xy = (0 + margin_left, ROW_HEIGHT)

    draw.text(main_xy, temp, "white", FONT_30_BOLD, "lm")
    draw.text(subt_xy, min_max, "lightgrey", FONT_20_BOLD, "la")


def draw_uv_info(draw: ImageDraw.ImageDraw, weather: WeatherData):
    uv_now, uv_max = (0 if uv == 0 else uv for uv in (weather.uv_index, weather.uv_index_daily_max))

    uv_now_str = f"\u2600{uv_now}"
    uv_max_str = f"\u2191{uv_max}"

    margin_right = 10
    main_xy = (720 - margin_right, get_vertical_center(0, ROW_HEIGHT))
    subt_xy = (720 - margin_right, ROW_HEIGHT)

    draw.text(main_xy, uv_now_str, "white", FONT_30_BOLD, "rm")
    draw.text(subt_xy, uv_max_str, "lightgrey", FONT_20_BOLD, "ra")


def draw_gui(departures: list[Departure], weather: WeatherData | None) -> Image.Image:
    image = Image.new("RGB", (720, 720), "black")
    draw = ImageDraw.Draw(image)
    draw_clock(draw)
    draw_weather_info(draw, weather)
    draw_trip_list(draw, departures)
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
    departures = fetch_departures_for_all_stations_concurrently()
    weather = get_weather()
    img = draw_gui(departures, weather)
    img.show()


def death_screen(error: str):
    text = "I died :("
    screen = Image.new("RGB", (720, 720), "black")
    draw = ImageDraw.Draw(screen)
    text_anchor = "mm"
    draw.text((360, 200), text, "red", FONT_50, text_anchor)
    draw.multiline_text((10, 300), error, "red", FONT_50, "la", spacing=2)
    write_rgb_to_frame_buffer(screen)
