# transit-display

Displays live public transit departures and current weather info on a kiosk-style screen, optimized for low-resource devices like the Raspberry Pi.

## Basics

- **Public transit**: Uses the [BVG API](https://v6.bvg.transport.rest/api.html) to fetch the public transit info, so it only works in Berlin and surrounding areas.
- **Weather data**: Uses [Open-meteo API](https://open-meteo.com) to fetch weather data.
- **Multithreading**: To update the on-screen components independently, dedicated background threads are implemented.
- **Lighweight rendering**: To avoid unnecessary overhead on the low-powered Pi Zero, the app does not use a high-level GUI framework and instead uses pixel coordinates to compose the interface as an image with [Pillow](https://pypi.org/project/pillow/), which is then written straight into the framebuffer.
- **Hardware-specific design**: This app was purpose-built for the Pimoroni Hyperpixel 4.0 Square Display (because I still had one from an old project), using its exact resolution and pixel format. While not flexible, targeting a specific known hardware allowed for efficient, low-overhead rendering and simplified development without having to bother with scaling logic or abstraction layers.

## Setup

### Your stations

Edit `stations.yaml` with the stations for which you want to see the next departures. The `fetch_products` field specifies what types of transport from that station you are interested in seeing departures for. Possible values are: "suburban", "subway", "tram", "bus", "ferry", "express", "regional".

You can find the stationID of your stations using the [BVG OpenAPI Playground](https://petstore.swagger.io/?url=https%3A%2F%2Fv6.bvg.transport.rest%2F.well-known%2Fservice-desc%0A). Use the `/locations` endpoint with a keyword query like "Hauptbahnhof", and copy the ID from the response JSON.

### Requirements

Install the requirements in the `requirements.txt`.

If using pip, you can just run

~~~bash
cd transit-display/
pip install -r requirements.txt
~~~

Some systems, like the headless Raspberry Pi OS, don't have pip installed. In that case, the easiest way to install the packages is

~~~bash
sudo apt update
sudo apt install python3-requests python3-yaml python3-numpy python3-pillow
~~~

## Usage

### Print departures to terminal

You can run trip_fetcher.py as a simple script to output the next departures as a table in the terminal.

~~~bash
cd transit-display
python transit_display/trip_fetcher.py
~~~

### Run GUI

To run the GUI, run the app as a Python module:

~~~bash
cd transit-display/
python -m transit_display.main
~~~

If you have a framebugger available at `/dev/fb0`, the GUI loop will launch and display on screen.

If you don't have that framebuffer available or no access to it, a static snapshot of the GUI will open in a preview window.

### Run as a service

To have the app run on startup and to restart and to restart it on exit, you can add it as a systemd service using the `transit-display.service` file.

1. In the `transit-display.service` file, change `USERNAME` to your username.
2. In the `transit-display.service` file, change the `WorkingDirectory` to the repo root location on your machine.
3. Copy the file over to `/etc/systemd/system/transit-display.service`.
4. Enable the service:

    ~~~bash
    sudo systemctl daemon-reexec
    ~~~

    ~~~bash
    sudo systemctl daemon-reload
    ~~~

    ~~~bash
    sudo systemctl enable transit-display.service
    ~~~

5. Start the service:

    ~~~bash
    sudo systemctl start transit-display.service
    ~~~

6. Check service status:

    ~~~bash
    sudo systemctl status transit-display.service
    ~~~

7. Check logs:

    ~~~bash
    journalctl -u transit-display.service -f
    ~~~

### Turn off cursor blinking

In headless mode, the cursor blinking of the terminal may continually overwrite some pixels in the framebuffer.

To turn this off, go to `/boot/firmware/cmdline.txt` (or `/boot/cmdline.txt` sometimes), append the following. Make sure the file contains only a single line!

~~~bash
# /boot/firmware/cmdline.txt or /boot/cmdline.txt
vt.global_cursor_default=0
~~~

Then reboot.
