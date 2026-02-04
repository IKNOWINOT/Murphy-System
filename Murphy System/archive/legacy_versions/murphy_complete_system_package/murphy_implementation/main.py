"""
Murphy System Main Application

This is the main entry point for the Murphy System.
It integrates all components and provides a unified interface.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

from .forms.api import router as forms_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Murphy System API",
    description="Form-driven task execution with Murphy validation and human-in-the-loop",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(forms_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Murphy System",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "forms": "/api/forms",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "murphy-system",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "forms": "operational",
            "validation": "operational",
            "execution": "operational",
            "hitl": "operational"
        }
    }


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    # TODO: Implement actual statistics tracking
    return {
        "total_forms_submitted": 0,
        "total_tasks_executed": 0,
        "total_validations": 0,
        "total_interventions": 0,
        "average_confidence": 0.0,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Murphy System...")
    
    uvicorn.run(
        "murphy_implementation.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )