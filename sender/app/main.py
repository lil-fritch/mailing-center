import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes import email
from app.core.errors import AppError
from app.core.logger import logger
from app.services.cleanup_service import screenshot_cleaner


async def cleanup_old_screenshots():
    """Cleanup screenshots older than 7 days"""
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    
    while True:
        try:
            result = await loop.run_in_executor(
                executor,
                lambda: screenshot_cleaner.cleanup(
                    older_than_days=7,
                    dry_run=False,
                    remove_empty_parents=True
                )
            )
            logger.info(f"Screenshot cleanup completed: {result['to_delete']} directories deleted, {result['total_runs']} total runs found")
        except Exception as e:
            logger.error(f"Error during screenshot cleanup: {e}", exc_info=True)
        
        # Wait 24 hours before next cleanup
        await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    cleanup_task = asyncio.create_task(cleanup_old_screenshots())
    logger.info("Scheduled screenshot cleanup task started (runs once per day)")
    yield
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Handle expected application errors"""
    return JSONResponse(
        status_code=400,
        content={
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred"
        }
    )


app.include_router(email.router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": settings.APP_NAME,
        "status": "running"
    }
