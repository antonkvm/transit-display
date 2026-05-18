import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from transit_display.trip_fetcher import Departure
from transit_display.weather_fetcher import WeatherData, get_weather

logger = logging.getLogger(__name__)

NUM_ROWS, ROW_HEIGHT = 18, 40  # these need to multiply to 720
COL_WIDTHS = [80, 460, 80, 100]  # these need to add up to 720
TOP_OFFSET_COLS = 6  # number of cols cleared at top of screen for clock/weather
FRAMEBUFFER = Path("/dev/fb0")

FONT_STYLE = str(Path(__file__).absolute().parent / "assets/DejaVuSans.ttf")
FONT_STYLE_BOLD = str(Path(__file__).absolute().parent / "assets/DejaVuSansCondensed-Bold.ttf")

SBAHN_GREEN = (0, 119, 52)
METROBUS_YELLOW = (233, 208, 33)
BUS_PURPLE = (160, 1, 121)
LATE_RED = (255, 0, 0)
EARLY_YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)


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

    draw.text((text_x, text_y), departure.line, text_color, font(30, bold=True), text_anchor)


def truncate_text(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> str:
    if draw.textlength(text, font) <= max_width:
        return text
    while draw.textlength(text + "...", font) > max_width:
        text = text[:-1]
    return text + "..."


def get_horizontal_center(left_x: int, offset_to_right: int):
    return left_x + offset_to_right // 2


def get_vertical_center(top_y: int, offset_downwards: int) -> int:
    return top_y + offset_downwards // 2


def draw_destination(departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int):
    text = departure.destination

    text_anchor = "lm"  # left-middle
    padding_left = 10
    text_x = x + padding_left
    text_y = get_vertical_center(y, ROW_HEIGHT)

    text = truncate_text(text, font(30), draw, col_width - padding_left)

    draw.text((text_x, text_y), text, "lightgrey", font(30), text_anchor)


def draw_depart_time(
    departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int, text_color: tuple[int, int, int]
):
    text = datetime.strftime(departure.when, "%H:%M")
    text_anchor = "rm"  # middle-middle
    padding_right = 5
    text_x = x + col_width - padding_right
    text_y = get_vertical_center(y, ROW_HEIGHT)

    draw.text((text_x, text_y), text, text_color, font(30, bold=True), text_anchor)


def draw_delay(
    departure: Departure, draw: ImageDraw.ImageDraw, x: int, y: int, col_width: int, text_color: tuple[int, int, int]
):
    text = f"{departure.delay_minutes_str}"
    text_anchor = "rm"
    padding_right = 0
    text_x = x + col_width - padding_right
    text_y = get_vertical_center(y, ROW_HEIGHT)
    draw.text((text_x, text_y), text, text_color, font(20, bold=True), text_anchor)


def draw_trip_list(draw: ImageDraw.ImageDraw, departures: list[Departure]):
    for row in range(TOP_OFFSET_COLS, NUM_ROWS):
        y = row * ROW_HEIGHT

        if row % 2 == 0:
            draw.rectangle(((0, y), (720, y + ROW_HEIGHT)), (25, 25, 25))

        try:
            departure = departures[row - TOP_OFFSET_COLS]
        except IndexError:
            # more rows than available departures, leave remaining rows empty
            break

        for col, col_width in enumerate(COL_WIDTHS):
            x = sum(COL_WIDTHS[:col])

            if departure.delay_minutes > 0:
                delay_color = LATE_RED
            elif departure.delay_minutes < 0:
                delay_color = EARLY_YELLOW
            else:
                delay_color = WHITE

            if col == 0:
                draw_line_info(departure, draw, x, y, col_width)
            elif col == 1:
                draw_destination(departure, draw, x, y, col_width)
            elif col == 2 and departure.delay_minutes != 0:
                draw_delay(departure, draw, x, y, col_width, delay_color)
            elif col == 3:
                draw_depart_time(departure, draw, x, y, col_width, delay_color)


def draw_clock(draw: ImageDraw.ImageDraw):
    now = datetime.now()
    # date_str = now.strftime("%a, %d. %b %Y")
    time_str = now.strftime("%H:%M")

    text_anchor = "la"
    x = 10
    y = ROW_HEIGHT

    draw.text((x, y), time_str, "white", font(160), text_anchor)


def draw_date(draw: ImageDraw.ImageDraw):
    now = datetime.now()
    date_str = now.strftime("%A, %d.%m.%Y")

    text_anchor = "la"
    x = 20
    y = 20

    draw.text((x, y), date_str, "white", font(35), text_anchor)


def draw_weather_info(draw: ImageDraw.ImageDraw, weather: WeatherData | None):
    if weather:
        draw_temperature_info(draw, weather)
        draw_uv_info(draw, weather)
    else:
        logger.warning("No weather data available to draw, leaving area blank")


def draw_temperature_info(draw: ImageDraw.ImageDraw, weather: WeatherData):
    temp = f"{weather.temperature}°"
    min_max = f"\u2191{weather.temperature_daily_max}° \u2193{weather.temperature_daily_min}°"

    margin_right = 10
    main_xy = (720 - margin_right, 0)
    subt_xy = (720 - margin_right, 70)

    draw.text(main_xy, temp, "white", font(60, bold=True), "ra")
    draw.text(subt_xy, min_max, "lightgrey", font(30, bold=True), "ra")


def draw_uv_info(draw: ImageDraw.ImageDraw, weather: WeatherData):
    uv_now, uv_max = (0 if uv == 0 else uv for uv in (weather.uv_index, weather.uv_index_daily_max))

    uv_now_str = f"\u2600{uv_now}"
    uv_max_str = f"\u2191{uv_max}"

    margin_right = 10
    main_xy = (720 - margin_right, ROW_HEIGHT * 3)
    subt_xy = (720 - margin_right, ROW_HEIGHT * 3 + 70)

    draw.text(main_xy, uv_now_str, "white", font(60, bold=True), "ra")
    draw.text(subt_xy, uv_max_str, "lightgrey", font(30, bold=True), "ra")


def draw_gui(departures: list[Departure], weather: WeatherData | None) -> Image.Image:
    image = Image.new("RGB", (720, 720), "black")
    draw = ImageDraw.Draw(image)
    draw_clock(draw)
    draw_date(draw)
    draw_weather_info(draw, weather)
    draw_trip_list(draw, departures)
    # draw_grid_outline_for_testing(draw)
    return image


def draw_grid_outline_for_testing(draw):
    for row in range(0, NUM_ROWS):
        y = row * ROW_HEIGHT
        for col, col_width in enumerate(COL_WIDTHS):
            x = sum(COL_WIDTHS[:col])
            draw.rectangle([(x, y), (x + col_width - 1, y + ROW_HEIGHT - 1)], outline="red")


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
    # departures = fetch_departures_for_all_stations_concurrently()
    logger.info("Assuming this is a test environemnt, using dummy departure list and creating a single snapshot.")
    departures = [
        Departure("1", "S41", "↻ S Beusselstr.", datetime.now() + timedelta(minutes=0), 60, 1, "+1", "suburban"),
        Departure("2", "S42", "↺ S Beusselstr.", datetime.now() + timedelta(minutes=1), 0, 0, "0", "suburban"),
        Departure("3", "M45", "Hertzallee", datetime.now() + timedelta(minutes=2), 0, 0, "0", "bus"),
        Departure("4", "M45", "Johannesstift", datetime.now() + timedelta(minutes=3), 0, 0, "0", "bus"),
        Departure("5", "S41", "↻ S Greifswalder Str.", datetime.now() + timedelta(minutes=4), 0, 0, "0", "suburban"),
        Departure("6", "S42", "↺ S Südkreuz Bhf", datetime.now() + timedelta(minutes=5), 0, 0, "0", "suburban"),
        Departure("7", "309", "U Wilmersdorfer Str.", datetime.now() + timedelta(minutes=6), -60, -1, "-1", "bus"),
        Departure("8", "S41", "↻ S Beusselstr.", datetime.now() + timedelta(minutes=7), 0, 0, "0", "suburban"),
        Departure("9", "M45", "Johannesstift", datetime.now() + timedelta(minutes=8), 0, 0, "0", "bus"),
        Departure("10", "139", "Eschenweg", datetime.now() + timedelta(minutes=9), 0, 0, "0", "bus"),
        Departure("11", "S42", "Meppen11", datetime.now() + timedelta(minutes=10), 0, 0, "0", "suburban"),
        Departure("12", "139", "Schlosspark-Klinik", datetime.now() + timedelta(minutes=11), 0, 0, "0", "bus"),
    ]
    weather = get_weather()
    img = draw_gui(departures, weather)
    img.show()


def death_screen(error: str):
    text = "I died :("
    screen = Image.new("RGB", (720, 720), "black")
    draw = ImageDraw.Draw(screen)
    text_anchor = "mm"
    draw.text((360, 200), text, "red", font(50), text_anchor)
    draw.multiline_text((10, 300), error, "red", font(50), "la", spacing=2)
    write_rgb_to_frame_buffer(screen)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font=FONT_STYLE_BOLD if bold else FONT_STYLE, size=size)
