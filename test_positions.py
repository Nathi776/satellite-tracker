#!/usr/bin/env python
import sys
sys.path.insert(0, "c:/Users/Prince/satellite-tracker")

from backend.services.tle_service import get_tles
from backend.services.orbit_service import get_satellite_position

tles = get_tles()
print(f"Total TLEs: {len(tles)}")

for i, (name, tle) in enumerate(list(tles.items())[:5]):
    print(f"\n{i+1}. {name}")
    print(f"   Line1: {tle.get('line1', 'MISSING')[:30]}...")
    print(f"   Line2: {tle.get('line2', 'MISSING')[:30]}...")
    pos = get_satellite_position(tle)
    if pos:
        print(f"   Position: lat={pos['lat']:.2f}, lon={pos['lon']:.2f}, alt={pos['alt_km']:.0f}km")
    else:
        print(f"   Position: FAILED")
