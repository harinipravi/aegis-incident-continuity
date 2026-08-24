import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aegis.config import settings
from aegis.routers.health import router as health_router
from aegis.routers.incidents import router as incidents_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Aegis Automated Incident Continuity & Root Cause Analysis Backend API",
    version="0.1.0",
    debug=settings.DEBUG
)

# Register routers
app.include_router(health_router)
app.include_router(incidents_router)
# Serve Aegis frontend
app.mount("/web", StaticFiles(directory="web"), name="web")


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse("web/index.html")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
