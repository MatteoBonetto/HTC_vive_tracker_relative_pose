from vive_provider import *
import socket
import time

vp = Vive_provider(1)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

server.settimeout(0.2)
server.bind(("", 44444))

while True:
    
    # temporary, converting to bytes
    # TODO protobuf
    trackerInfo = str(vp.getTrackerInfo(1))
    trackerInfo = trackerInfo.encode('UTF-8')
    
    server.sendto(trackerInfo, ('<broadcast>', 37020))
    time.sleep(0.1)


