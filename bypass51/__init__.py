import sys
import bypass451
for attr in dir(bypass451):
    globals()[attr] = getattr(bypass451, attr)
sys.modules["bypass51"] = bypass451
