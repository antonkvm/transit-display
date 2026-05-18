from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import transit_display.db_handler as db_handler

app = FastAPI()

WORKING_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=WORKING_DIR / "templates/")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "base.htmx")


@app.get("/weather", response_class=HTMLResponse)
def weather(request: Request):
    return templates.TemplateResponse(request, "weather_config.htmx")


@app.get("/transit", response_class=HTMLResponse)
def transit():
    return "Transit config goes here"


@app.post("/weather/set_coords", response_class=HTMLResponse)
def set_weather_coords(name: Annotated[str, Form()], lat: Annotated[float, Form()], lon: Annotated[float, Form()]):
    if not 1 <= len(name) <= 255:
        return "Invalid length for name field."
    elif not -90 <= lat <= 90:
        return "Invalid latitude value."
    elif not -180 <= lon <= 180:
        return "Invalid longitude value"
    db_handler.insert_weather_coords(name, lat, lon)
    return HTMLResponse("Success!", headers={"HX-Trigger": "weatherUpdated"})


@app.get("/weather/get_coords", response_class=HTMLResponse)
def get_weather_coords():
    weather_coords = db_handler.get_weather_coords()
    return f"""
    <table>
        <tr>
            <td>Name:</td>
            <td>{weather_coords["name"]}</td>
        </tr>
        <tr>
            <td>Latitude</td>
            <td>{weather_coords["lat"]}</td>
        </tr>
        <tr>
            <td>Latitude</td>
            <td>{weather_coords["lon"]}</td>
        </tr>
    </table>
    """

@app.get("/gui", response_class=HTMLResponse)
def show_gui():
    # draw gui image and return as png
    # gui_img = draw_gui()
    pass
