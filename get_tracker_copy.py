#!/usr/bin/env python

import json
from gc import collect
from vive_pb2 import *
from transforms3d import euler
from transforms3d.euler import mat2euler
from transforms3d.quaternions import quat2mat

import argparse
from datetime import datetime
import socket
import time
from vive_utils import *
from vive_provider import *
import os

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
    
    trackers_before_mv = vp.get_tracker_infos()
    print("Move forks!!")
    # Wait for the user to press enter
    input("Press Enter when you finished...")
    trackers_after_mv = vp.get_tracker_infos()
    dist_th = 0.1
    fork_id = []
    pallet_id = -1
    for id_before_mv in trackers_before_mv["trackers"]:
        for id_after_mv in trackers_after_mv["trackers"]:
            if id_before_mv == id_after_mv:
                p_before = trackers_before_mv["trackers"][id_before_mv]["position"]
                p_after = trackers_after_mv["trackers"][id_before_mv]["position"]
                if any(abs(p_before[i] - p_after[i]) > dist_th for i in range(1, 3)):
                    fork_id.append(id_before_mv)
                else:
                    pallet_id = id_before_mv

    if(len(fork_id)==0):
        print("ERROR forks not detected")
        sys.exit(0)
    if(pallet_id==-1):
        print("ERROR pallet not detected")
        sys.exit(0)

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
            os.system('clear')
            print("---")
            print("* Tracking %d devices (%d detections made)" % (len(trackers["trackers"]), len(collection.messages)))
            p_fork = [0, 0, 0]
            for id in trackers["trackers"]:
                p = trackers["trackers"][id]["position"]
                if(id in fork_id):
                    p_fork = p_fork + p
                    quat_fork = trackers["trackers"][id]["orientation"]
                else: 
                    if id == pallet_id:
                        p_pallet = p
                        quat_pallet = trackers["trackers"][id]["orientation"]
            p_fork = p_fork / len(fork_id)
                	
            print()
            # construct fork homogeneous matrix
            T_fork = np.eye(4)
            T_fork[:3, :3] = quat2mat(quat_fork)
            T_fork[:3, 3] = p_fork
            # construct pallet homogeneous matrix
            T_pallet = np.eye(4)
            T_pallet[:3, :3] = quat2mat(quat_pallet)
            T_pallet[:3, 3] = p_pallet

            T_fork_pallet = np.dot(T_pallet, np.linalg.inv(T_fork))
            # Extract translation and rotation components from T_fork_pallet
            t_fork_pallet = T_fork_pallet[:3, 3]  # Translation vector
            R_fork_pallet = T_fork_pallet[:3, :3]  # Rotation matrix
    
            # Compute Euclidean distance for translation
            d_translation = np.linalg.norm(t_fork_pallet)
            # difference rotation quaternion
            euler_differences = mat2euler(R_fork_pallet, axes='sxyz') #The first angle is the rotation about the Z axis with sign. The second angle is the rotation about the Y axis with sign. The third angle is the rotation about the X axis with sign.
            euler_differences_deg = (euler_differences[2] * 180 / math.pi, euler_differences[1] * 180 / math.pi, euler_differences[0] * 180 / math.pi)

            p_diff = p_pallet - p_fork
            # Show results
            print("T_fork")
            print(T_fork)
            print("inv_T_fork")
            print(np.linalg.inv(T_fork))
            print("T_pallet")
            print(T_pallet)
            print("T_fork_pallet")
            print(T_fork_pallet)
            print("Euclidean distance from forks to pallet: %g" % d_translation)
            print("distance components from forks to pallet")
            print("  - x: %g, y: %g, z: %g" % (t_fork_pallet[0], t_fork_pallet[1], t_fork_pallet[2]))
            print("  - x: %g, y: %g, z: %g" % (p_diff[0], p_diff[1], p_diff[2]))
            print("Rotation in degrees  from forks to pallet")
            print("  - roll: %g, pitch: %f, yaw: %g" % tuple(euler_differences_deg))

            # Add timestamp to matrices and append to file
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("rototranslation_matrices.txt", "a") as f:
                f.write(f"\nTimestamp: {current_time}\n")
                f.write("matrix:\n")
                np.savetxt(f, T_fork_pallet, fmt="%.6f", delimiter=" ")

            pb_msg.ClearField("tagged_positions")

except KeyboardInterrupt:
    print("Terminated by KeyboardInterrupt")
