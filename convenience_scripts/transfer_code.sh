#!/bin/bash

# short convenience script to transfer code to transit-display and restart the service
# depends on transit-display.service being set up on the remote machine
# also depends on ssh config for transit-display


scp -r ~/Code/transit-display/transit_display anton@transit-display:/home/anton/transit-display

ssh anton@transit-display 'sudo systemctl restart transit-display.service; journalctl -u transit-display.service -f -o cat'