from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
#from backend.satellites import get_iss_position
from backend.passes import predict_passes
from backend.passes_african import predict_african_passes
from backend.positions import get_all_positions, ISS_TLE

from backend.services.groundtrack import get_ground_track
from backend.services.tle_service import get_tles
from backend.services.orbit_service import get_satellite_position
from backend.satellites.african import AFRICAN_SATELLITES


app = FastAPI(title='African Satellite Tracker')

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")  
def root():
    return {"message": "Satellite Tracker API is running."}

@app.get("/groundtrack/{satellite_name}")
def ground_track(satellite_name: str):
    # Support ISS plus the listed African satellites
    if satellite_name == "ISS":
        tle = ISS_TLE
    elif satellite_name in AFRICAN_SATELLITES:
        tle = AFRICAN_SATELLITES[satellite_name]["tle"]
    else:
        return {"error": "Satellite not found"}

    track = get_ground_track(tle)

    return {
        "satellite": satellite_name,
        "track": track
    }


@app.get("/passes/african/{satellite_name}")
def african_passes(satellite_name):
    return predict_african_passes(satellite_name)

@app.get("/passes/iss")
def iss_passes():
    passes = predict_passes()
    return {
        "city": "Pretoria",
        "satellite": "ISS",
        "passes": passes
    }

@app.get("/iss")
def iss_position():
    return get_iss_position()

@app.get("/positions")
def get_positions():
    tles = get_tles()
    results = []

    for name, tle in list(tles.items())[:20]:  # limit for performance
        pos = get_satellite_position(tle)
        if pos:
            results.append({
                "name": name,
                **pos
            })

    return results

@app.get("/satellite/{name}")
def get_satellite(name: str):
    tle = get_tle_by_name(name)

    if not tle:
        raise HTTPException(status_code=404, detail="Satellite not found")

    position = get_satellite_position(tle)
    return {
        "name": tle["name"],
        "position": position
    }