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

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(18, GPIO.OUT)

os.system("sudo hciconfig hci0 down")
os.system("sudo hciconfig hci0 up")

if not os.geteuid() == 0:
    sys.exit("script only works as root")

btlib = find_library("bluetooth")
if not btlib:
    raise Exception(
        "Can't find required bluetooth libraries"
        " (need to install bluez)"
    )
bluez = CDLL(btlib, use_errno=True)

dev_id = bluez.hci_get_route(None)

sock = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI)
sock.bind((dev_id,))

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
sock.setsockopt(SOL_HCI, HCI_FILTER, hci_filter)

err = bluez.hci_le_set_scan_enable(
    sock.fileno(),
    1,  # 1 - turn on;  0 - turn off
    0, # 0-filtering disabled, 1-filter out duplicates
    5000  # timeout
)
if err < 0:
    GPIO.output(18,False)
    errnum = get_errno()
    raise Exception("{} {}".format(
        errno.errorcode[errnum],
        os.strerror(errnum)
    ))

with open("/home/pi/Documents/BeaconScanner/beacons") as f:
    beacons = f.read().splitlines()

devices = []

def beacontimer():
    global devices
    isBeacon = False
    try:
        if not devices:
            print("\033[91m" + "no devices" + "\033[0m")
            GPIO.output(18,False)
        else:
            for d in list(set(devices)):
                if d in beacons:
                    print("\033[92m" + d + "\033[0m")
                    isBeacon = True
                else:
                    print(d)

            if isBeacon:
                GPIO.output(18,True)
            else:
                GPIO.output(18,False)
                    
            devices = []
    except:
        GPIO.output(18,False)

    print("----------")
    
    threading.Timer(2, beacontimer).start()

beacontimer()

while True:
    data = sock.recv(1024)
    # get bluetooth address from LE Advert packet
    ba = ':'.join("{0:02x}".format(x) for x in data[12:6:-1])
    devices.append(ba)
