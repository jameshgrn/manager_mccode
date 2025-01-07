from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import logging
from pathlib import Path

from manager_mccode.services.metrics import MetricsCollector
from manager_mccode.services.database import DatabaseManager
from manager_mccode.config.settings import Settings

logger = logging.getLogger(__name__)
app = FastAPI(title="Manager McCode Dashboard")

# Setup templates and static files
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# Initialize services
settings = Settings()
db = DatabaseManager(settings.DEFAULT_DB_PATH)
db.initialize()  # Ensure tables exist
metrics = MetricsCollector(db)

@app.get("/")
async def dashboard(request: Request):
    """Main dashboard view"""
    try:
        # Get today's metrics
        today = datetime.now()
        daily_metrics = metrics.get_daily_metrics(today)
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "metrics": daily_metrics,
                "date": today.strftime("%Y-%m-%d")
            }
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/daily/{date}")
async def get_daily_metrics(date: str):
    """Get metrics for a specific date"""
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        return metrics.get_daily_metrics(date_obj)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    except Exception as e:
        logger.error(f"Error getting daily metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/range")
async def get_metrics_range(start: str, end: str):
    """Get metrics for a date range"""
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        return metrics.export_timeframe(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    except Exception as e:
        logger.error(f"Error getting metrics range: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"}
    )

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    ) 