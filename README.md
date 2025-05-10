# transit-display

Display the the next public transit departures from you favorite stations on a kiosk-style screen.

## Some info

Uses the [BVG API](https://v6.bvg.transport.rest/api.html) to fetch the public transit info, so it only works in Berlin and surrounding areas.

Intended to be used with the Pimoroni Hyperpixel 4.0 Square Display, so the resolution is hard coded to 720x720.

The app writes the GUI directly to the framebuffer at `/dev/fb0` as a byte array in BGRa pixel format ('reverse' RGB). This mode is used bc its what the Pimoroni display says it wants when running `fbset -fb /dev/fb0`.

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

### Run on Raspberry Pi with Pimeroni Square Disaply

Set up the Pimoroni display and the Pi. Headless Pi OS works fine.

The Pimoroni setup for this display with older Pi models (like the Zero WH that I use) is a bit messy, but I got it to work with Pi OS Bookworm and Pimoroni legacy drivers, installed with their helper script. Check this [GitHub issue](https://github.com/pimoroni/hyperpixel4/issues/177) for more info.

To run the GUI, you have to run it as a Python module:

~~~bash
cd transit-display/
python -m transit_display.gui
~~~

If you have a framebuffer `/dev/fb0` available, it will start the app with the fullscreen GUI. If not, then it will try to open a image preview window with as static snapshot of the GUI.

You can kill the process as expected with `ctrl+c`.

### Run as a service

To have the app run on startup and to restart and to restart it on exit, you can add it as a systemd service using the `transit-display.service` file.

### Steps

In the `transit-display.service` file, change `USERNAME` to your username.

In the `transit-display.service` file, change `WorkingDirectory` to the repo root location on your machine.

Then copy the file over to `/etc/systemd/system/transit-display.service`.

Enable the service:

~~~bash
sudo systemctl daemon-reexec
~~~

~~~bash
sudo systemctl daemon-reload
~~~

~~~bash
sudo systemctl enable transit-display.service
~~~

Start the service:

~~~bash
sudo systemctl start transit-display.service
~~~

Check service status:

~~~bash
sudo systemctl status transit-display.service
~~~

Check logs:

~~~bash
journalctl -u transit-display.service -f
~~~

### Turn off cursor blinking

Even in headless mode, the terminal will be shown, and even if nothing happens, the blinking cursor will write into the framebuffer and be visible.

To turn this off, go to `/boot/firmware/cmdline.txt` (or `/boot/cmdline.txt` sometimes), append the following. Make sure the file contains only a single line!

~~~txt
vt.global_cursor_default=0
~~~

Then reboot.
