import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def wifi_connected(conn_name: str) -> bool:
    try:
        out = subprocess.check_output(["nmcli", "--get-values", "connection,state", "device"])
        out = out.decode("ASCII")
        for device in out.splitlines():
            name, state = device.split(":", 1)
            if name == conn_name and state == "connected":
                return True
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Wifi check using nmcli failed: {e}")
        raise


def get_wifi_connection_name() -> str:
    """Get the nmcli name for the machine's wifi connection. Raise RuntimeError if  no wifi connection was found."""
    try:
        conns = subprocess.check_output(["nmcli", "--get-values", "name,device,type", "con", "show", "--active"])
        conns = conns.decode("ASCII")
        for conn in conns.splitlines():
            name, device, device_type = conn.split(":", 2)
            if device.startswith("wlan") and "wireless" in device_type:
                return name
        raise RuntimeError("No wifi connection found using nmcli.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to use nmcli to get wifi connection name: {e}")
        raise


def reconnect_wifi(conn_name: str):
    pass


def has_internet() -> bool:
    pass


#todo: I am checking wifi status again after I confirmed it was down, that's reduntant.
def try_reconnect_loop(conn_name: str):
    attempts = 0
    retry_delay = 10
    while not has_internet() and not wifi_connected(conn_name):
        if attempts > 10:
            retry_delay = 60
        elif attempts > 20:
            raise RuntimeError(f"Max retries ({attempts}) exceeded for wifi reconnect.")
        logger.error("Wifi seems to be down. Trying to reconnect...")
        reconnect_wifi(conn_name)
        time.sleep(retry_delay)
    else:
        logger.info("Wifi connection reestablished.")


# todo: this loop runs on a thread and if wifi is down should cause a hint on the GUI
def wifi_check_loop():
    wifi_conn = get_wifi_connection_name()

    while True:
        if not has_internet() and not wifi_connected(wifi_conn):
            try_reconnect_loop(wifi_conn)
        time.sleep(30)
