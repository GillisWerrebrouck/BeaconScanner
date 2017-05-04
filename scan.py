import sys
import os
import struct
from ctypes import (CDLL, get_errno)
from ctypes.util import find_library
from socket import (
    socket,
    AF_BLUETOOTH,
    SOCK_RAW,
    BTPROTO_HCI,
    SOL_HCI,
    HCI_FILTER,
)
import RPi.GPIO as GPIO
import time, threading

# set mode to BCM to use GPIO numbers
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
# set pin 18 as an output
GPIO.setup(18, GPIO.OUT)

# set the bluetooth interface down and up
# if this is not done the script will crash the second time you run it
os.system("sudo hciconfig hci0 down")
os.system("sudo hciconfig hci0 up")

# check if the user has root permissions
if not os.geteuid() == 0:
    sys.exit("script only works as root")

# check if a bluetooth stack like bluez is present
btlib = find_library("bluetooth")
if not btlib:
    raise Exception(
        "Can't find required bluetooth libraries"
        " (need to install bluez)"
    )
bluez = CDLL(btlib, use_errno=True)

dev_id = bluez.hci_get_route(None)

# configure the bluetooth socket
sock = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI)
sock.bind((dev_id,))

# set le scan parameters
err = bluez.hci_le_set_scan_parameters(sock.fileno(), 0, 0x10, 0x10, 0, 0, 1000);
if err < 0:
    # occurs when scanning is still enabled from previous call
    raise Exception("Set scan parameters failed")

# allows LE advertising events
hci_filter = struct.pack(
    "<IQH", 
    0x00000010, 
    0x4000000000000000, 
    0
)
# set the socket options with the filter
sock.setsockopt(SOL_HCI, HCI_FILTER, hci_filter)

err = bluez.hci_le_set_scan_enable(
    sock.fileno(),
    1,  # 1 - turn on;  0 - turn off
    0, # 0-filtering disabled, 1-filter out duplicates
    500  # timeout
)
if err < 0:
    # turn off led
    GPIO.output(18,False)
    errnum = get_errno()
    raise Exception("{} {}".format(
        errno.errorcode[errnum],
        os.strerror(errnum)
    ))

# read all mac addresses from the 'beacons' file
with open("/home/pi/Documents/BeaconScanner/beacons") as f:
    beacons = f.read().splitlines()

devices = []

# get the received data from the bluetooth socket
# filter the mac address and add to devices
while True:
    data = sock.recv(1024)
    # get bluetooth address from LE Advert packet
    ba = ':'.join("{0:02x}".format(x) for x in data[12:6:-1])
    devices.append(ba)

# define a method to check if a beacon is in range
def beacontimer():
    global devices
    isBeacon = False
    try:
        # check if there are mac addresses in devices
        if not devices:
            print("\033[91m" + "no devices" + "\033[0m")
            # turn off led
            GPIO.output(18,False)
        else:
            # loop through all devices
            # filter out duplicates by putting devices in a set and then again in a list
            for d in list(set(devices)):
                if d in beacons:
                    print("\033[92m" + d + "\033[0m")
                    isBeacon = True
                else:
                    print(d)

            # turn on/off led
            if isBeacon:
                GPIO.output(18,True)
            else:
                GPIO.output(18,False)

            # make the devices list empty   
            devices = []
    except:
        # turn off led
        GPIO.output(18,False)

    print("----------")

    # run the function each second
    threading.Timer(2, beacontimer).start()

# start the timer
beacontimer()