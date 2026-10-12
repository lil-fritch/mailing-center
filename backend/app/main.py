import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.emails import router as campaign_router
from app.api.b2b import router as b2b_router
from app.api.sender_accounts import router as sender_accounts_router
from app.api.auth import router as auth_router
from app.core.security import require_auth
from app.core.exceptions import AppError
from app.core.logger import get_logger
from app.core.settings import settings
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from app.database.connection import SessionLocal
from app.database.crud import CampaignCRUD

get_logger() 


@asynccontextmanager
async def lifespan(app: FastAPI):
	# Startup
	import asyncio
	logging.info("App lifespan startup: launching inbound loops (IMAP enabled in all modes)")
	from app.services.inbound_processor import processor

	async def _poll_loop():
		while True:
			logging.info("Tick: IMAP poll starting")
			await processor.run_polling_once()
			logging.info("Tick: IMAP poll done")
			await asyncio.sleep(60)

	async def _dispatch_loop():
		while True:
			logging.info("Tick: dispatch starting")
			await processor.dispatch_due()
			logging.info("Tick: dispatch done")
			await asyncio.sleep(30)

	tasks = [
		asyncio.create_task(_poll_loop()),
		asyncio.create_task(_dispatch_loop()),
	]
	try:
		yield
	finally:
		for t in tasks:
			t.cancel()


app = FastAPI(
	title="Mailing Center API",
	description="Email campaign management system with AI-powered content generation",
	version="1.0.0",
	lifespan=lifespan
)

# Include routers with tags for organized documentation
app.include_router(auth_router, prefix="/api", tags=["Authentication"])
app.include_router(campaign_router, prefix="/api", tags=["Campaigns"], dependencies=[Depends(require_auth)])
app.include_router(b2b_router, prefix="/api", tags=["B2B Objects"], dependencies=[Depends(require_auth)])
app.include_router(sender_accounts_router, prefix="/api", tags=["Sender Accounts"], dependencies=[Depends(require_auth)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://aipisarz.pl"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
def health_check():
	"""Health check endpoint"""
	return {"status": "healthy", "service": "mailing_center"}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
	logging.warning("%s %s", exc.status_code, exc.msg)
	return JSONResponse(
		status_code=exc.status_code,
		content={"detail": exc.msg},
	)


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
	logging.exception("Unhandled error: %s", exc)
	return JSONResponse(
		status_code=500,
		content={
			"detail": f"Internal Server Error: {str(exc)}",
		},
	)
