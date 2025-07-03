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


# time will tell if the permissions for this command work. When wifi disconnects again, I will check the logs.
def reconnect_wifi(conn_name: str):
    try:
        subprocess.run(["sudo", "nmcli", "connection", "up", conn_name], check=True)
        logger.info(f'Restarted wifi connection named "{conn_name}" using nmcli.')
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart wifi using nmcli: {e}")
        raise


def try_reconnect_loop(conn_name: str):
    attempts = 0
    retry_delay = 10
    while True:
        if attempts > 10:
            retry_delay = 60
        elif attempts > 20:
            raise RuntimeError(f"Max retries ({attempts}) exceeded for wifi reconnect.")
        logger.error("Wifi seems to be down. Trying to reconnect...")
        reconnect_wifi(conn_name)
        if wifi_connected(conn_name):
            logger.info("Wifi connection reestablished.")
            break
        time.sleep(retry_delay)


# todo: this loop runs on a thread and if wifi is down should cause a hint on the GUI
def wifi_check_loop():
    wifi_conn = get_wifi_connection_name()

    while True:
        if not wifi_connected(wifi_conn):
            logger.error("Wifi test indicated lost connection, attempting to reconnect...")
            try_reconnect_loop(wifi_conn)
        time.sleep(30)
