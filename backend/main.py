from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
#from backend.satellites import get_iss_position
from backend.passes import predict_passes
from backend.passes_african import predict_african_passes
from backend.positions import get_all_positions

from backend.services.groundtrack import get_ground_track
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
    if satellite_name not in AFRICAN_SATELLITES:
        return {"error": "Satellite not found"}

    tle = AFRICAN_SATELLITES[satellite_name]["tle"]

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
def positions():
    return get_all_positions()

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