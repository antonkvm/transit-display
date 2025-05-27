import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def wifi_connected() -> bool:
    conn_name = get_wifi_connection_name()
    try:
        out = subprocess.check_output(["nmcli", "--get-values", "connection,state", "device"])
        out = out.decode("ASCII")
        for device in out.splitlines():
            name, state = device.split(":", 1)
            if name == conn_name and state == "connected":
                return True
        logger.warning("No wifi!")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Wifi check using nmcli failed: {e}")
        raise

def get_wifi_connection_name() -> str | None:
    """Get the nmcli name for the machine's wifi connection, or None if no wifi connection was found."""
    try:
        out = subprocess.check_output(["nmcli", "--get-values", "name,device,type", "con", "show", "--active"])
        out = out.decode("ASCII")
        for line in out.splitlines():
            name, device, device_type = line.split(":", 2)
            if device.startswith("wlan") and "wireless" in device_type:
                return name
        raise RuntimeError('No wifi connection found using nmcli.')           
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to use nmcli to get wifi connection name: {e}")
        raise

def reconnect_wifi():
    pass


def wifi_check_loop():
    # do first wifi check 60 seconds after startup:
    time.sleep(60)
    while True:
        if not wifi_connected():
            reconnect_wifi()
        time.sleep(30)