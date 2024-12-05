#!/usr/bin/env python

import json
from gc import collect
from vive_pb2 import *
from transforms3d import euler

import argparse
from datetime import datetime
import socket
import time
from vive_utils import *
from vive_provider import *

parser = argparse.ArgumentParser()
parser.add_argument("--max_freq", "-f", type=int, default=250)
args = parser.parse_args()

collection = GlobalCollection()

try:
    vp = ViveProvider()

    pb_msg: GlobalMsg = GlobalMsg()
    last_broadcast: float = time.time()
    sequence: int = 0
    period: float = 1.0 / args.max_freq
    last: float = 0

    while True:
        # Limitting frequency
        elapsed = time.time() - last
        if elapsed < period:
            time.sleep(period - elapsed)
        last = time.time()

        # Collecting messages at maximum speed
        trackers = vp.get_tracker_infos()
        pb_msg.seq = sequence
        sequence += 1
        collection.messages.extend([pb_msg])

        if len(collection.tagged_positions) == 0:
            tagged_positions_to_message(trackers, collection)

            # Output debug infos
            print("---")
            print("* Tracking %d devices (%d detections made)" % (len(trackers["trackers"]), len(collection.messages)))
            for id in trackers["trackers"]:
                p = trackers["trackers"][id]["position"]
                rpy = euler.quat2euler(trackers["trackers"][id]["orientation"])
                rpy_deg = (rpy[0] * 180 / math.pi, rpy[1] * 180 / math.pi, rpy[2] * 180 / math.pi)
                print("- %s (%s)" % (id, trackers["trackers"][id]["device_type"]))
                print("  - x: %g, y: %g, z: %g" % (p[0], p[1], p[2]))
                print("  Rotation in radians :")
                print("  - roll: %g, pitch: %f, yaw: %g" % tuple(rpy))
                print("  Rotation in degrees :")
                print("  - roll: %g, pitch: %f, yaw: %g" % tuple(rpy_deg))
            print()

            pb_msg.ClearField("tagged_positions")

except KeyboardInterrupt:
    # Writing logs to binary file
    fname = datetime.now().strftime("%Y_%m_%d-%Hh%Mm%Ss") + "_vive.bin"
    print("Interrupted, saving the collection to %s ..." % fname)
    f = open("logs/" + fname, "wb")
    s = collection.SerializeToString()
    print(s)
    f.write(s)
    f.close()
