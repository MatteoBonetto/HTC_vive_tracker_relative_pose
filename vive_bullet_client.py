from vive_bullet import *

vive = Vive_provider(clientMode=True)
viewer = BulletViewer(vive)
viewer.physics = False
viewer.execute()