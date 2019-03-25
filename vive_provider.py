#!/usr/bin/python3
import sys
import time
import openvr
import math
import sys
import json
import numpy as np
from utils import *
import  numpy.linalg as linalg
import os

class Calib:
    def __init__(self, calibFilePath):
        self.calibration = None
        loaded = False
        if os.path.exists(calibFilePath):
            with open(calibFilePath, "r") as calibFile:
                self.calibration = json.loads(calibFile.read())
                loaded = True
            for id in self.calibration:
                self.calibration[id] = np.mat(self.calibration[id])
        else:
            print("! WARNING: Calibration file not found")


    def transform_frame(self, references, trackerToWorld):
        if self.calibration is None:
            return trackerToWorld

        # return self.calibration['worldToField']*trackerToWorld

        for id in references:
            if id in self.calibration:
                referenceToWorld = references[id]
                fieldToReference = self.calibration[id]

                trackerToReference = np.linalg.inv(referenceToWorld)*trackerToWorld
                trackerToField = np.linalg.inv(fieldToReference)*trackerToReference
                # print(str(id)+' '+str(trackerToReference))
                return trackerToField
        
        print('! ERROR: Cant find a suitable reference!')
        exit()

class Tracker:

    def __init__(self, serial_number, device_type, openvr_id):
        self.serial_number = serial_number
        self.device_type = device_type
        self.openvr_id = openvr_id
        

    
class Vive_provider:
    
    def __init__(self, enableButtons=False, calibFilePath="calibFile.json"):
        
        self.vr = openvr.init(openvr.VRApplication_Other)
        self.trackers = {}
        self.references = {}
        self.lastInfos = {}
        self.enableButtons = enableButtons
        
        self.calib = Calib(calibFilePath)
            
        self.scanTrackers()

    def scanTrackers(self):
        
        poses = self.vr.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
        ids = {}
        
        for i in range(1, openvr.k_unMaxTrackedDeviceCount):
            pose = poses[i]
            if not pose.bDeviceIsConnected:
                continue
            if not pose.bPoseIsValid:
                continue
            
            device_class = openvr.VRSystem().getTrackedDeviceClass(i)
            serial_number = openvr.VRSystem().getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String).decode('UTF-8')

            if(device_class == openvr.TrackedDeviceClass_GenericTracker or device_class == openvr.TrackedDeviceClass_Controller):
                if device_class == openvr.TrackedDeviceClass_Controller:
                    device_type = "controller"
                else:
                    device_type = "tracker"
                    
                t = Tracker(serial_number, device_type, i)
                
                self.trackers[serial_number] = t
            elif device_class == openvr.TrackedDeviceClass_TrackingReference:
                self.references[serial_number] = i
                
    def getTrackersInfos(self, raw=False):
        
        pose = self.vr.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
        ret = {}
        
        ret['vive_timestamp'] = int(time.perf_counter()*1000000)
        ret['time_since_epoch'] = int(time.time()*1000000)

        references = {}
        for r in self.references:
            openvr_id = self.references[r]
            currentTracker = pose[openvr_id]
    
            p = currentTracker.mDeviceToAbsoluteTracking
            m = np.matrix([list(p[0]), list(p[1]), list(p[2])])
            m = np.vstack((m, [0, 0, 0, 1]))
            corrected = m

            # if not raw:
            #     corrected = self.calib.get_transformation_matrix()*m

            references[r] = corrected
        ret["references"] = references

        trackersDict = {}
        
        for t in self.trackers.values():
            currentTrackerDict = {}
            
            currentTracker = pose[t.openvr_id]
    
            p = currentTracker.mDeviceToAbsoluteTracking
            m = np.matrix([list(p[0]), list(p[1]), list(p[2])])
            m = np.vstack((m, [0, 0, 0, 1]))
            corrected = m

            if not raw:
                if t.device_type == 'tracker':
                    Rz = np.matrix([
                        [math.cos(math.pi/2), -math.sin(math.pi/2), 0, 0],
                        [math.sin(math.pi/2), math.cos(math.pi/2), 0, 0],
                        [0, 0, 1, 0],
                        [0, 0, 0, 1]])
                    m = m*Rz
                corrected = self.calib.transform_frame(references, m)

            if t.device_type == 'controller':
                T = np.matrix([
                    [1, 0, 0, 0],
                    [0, 1, 0, -0.025],
                    [0, 0, 1, -0.025],
                    [0, 0, 0, 1]])
                corrected = corrected*T

            currentTrackerDict['openvr_id'] = t.openvr_id
            currentTrackerDict['serial_number'] = t.serial_number
            currentTrackerDict['device_type'] = t.device_type
            currentTrackerDict['pose'] = convert_to_quaternion(np.array(corrected[:3, :4]))
            currentTrackerDict['pose_matrix'] = corrected
            currentTrackerDict['velocity'] = [currentTracker.vVelocity[0], currentTracker.vVelocity[1], currentTracker.vVelocity[2]]
            currentTrackerDict['angular_velocity'] = [currentTracker.vAngularVelocity[0], currentTracker.vAngularVelocity[1], currentTracker.vAngularVelocity[2]]
            
            if(currentTracker.bPoseIsValid or not self.lastInfos): # if first iteration, lastInfos is empty
                currentTrackerDict['vive_timestamp_last_tracked'] = ret['vive_timestamp']
                currentTrackerDict['time_since_last_tracked'] = 0
            else:
                currentTrackerDict['vive_timestamp_last_tracked'] = self.lastInfos["trackers"][t.serial_number]['vive_timestamp_last_tracked']
                currentTrackerDict['time_since_last_tracked'] = ret['vive_timestamp'] - self.lastInfos['trackers'][t.serial_number]['vive_timestamp_last_tracked']

            if self.enableButtons:
                if currentTrackerDict['device_type'] == 'controller':
                    _, state = self.vr.getControllerState(t.openvr_id)
                    currentTrackerDict['buttonPressed'] = (state.ulButtonPressed != 0)

            
            trackersDict[t.serial_number] = currentTrackerDict
                     
        ret["trackers"] = trackersDict

        references_corrected = {}
        for id in references:
            references_corrected[id] = self.calib.transform_frame(references, references[id])

        ret["references_corrected"] = references_corrected

        self.lastInfos = ret.copy()
            
        return ret

    def vibrate(self, serial, duration=250):
        openvr_id = self.trackers[serial].openvr_id
        for x in range(duration): 
            self.vr.triggerHapticPulse(openvr_id, 0, 5000)
            time.sleep(0.001) 
    
    def getControllersInfos(self, raw=False):
        controllers = []
        trackers = self.getTrackersInfos(raw)['trackers']

        for t in self.trackers.values():
            if(str(t.device_type) == "controller"):
                controllers.append(trackers[t.serial_number])

        return controllers
                
