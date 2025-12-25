from fastapi import FastAPI
#from backend.satellites import get_iss_position
from backend.passes import predict_passes
from backend.passes_african import predict_african_passes
from backend.positions import get_all_positions

app = FastAPI(title='African Satellite Tracker')

@app.get("/")  
def root():
    return {"message": "Satellite Tracker API is running."}

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