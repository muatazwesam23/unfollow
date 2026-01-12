"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database.database import init_db, engine, Base, AsyncSessionLocal
from .database.models import User, UserRole
from .api.auth import hash_password
from .api.routes_auth import router as auth_router
from .api.routes_admin import router as admin_router
from .api.routes_servers import router as servers_router
from .api.routes_user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("[*] Starting VPN Tunnel API...")
    
    # Initialize database
    await init_db()
    print("[+] Database initialized")
    
    # Create default admin user if not exists
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role=UserRole.ADMIN.value,
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            await db.commit()
            print(f"[+] Default admin user created: {settings.ADMIN_USERNAME}")
        else:
            print(f"[+] Admin user exists: {settings.ADMIN_USERNAME}")
    
    print("[+] VPN Tunnel API ready!")
    
    yield
    
    # Shutdown
    print("[-] Shutting down VPN Tunnel API...")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    VPN Tunnel Backend API
    
    Complete backend for VPN Tunnel application with:
    - User authentication and management
    - Server management
    - Connection tracking
    - Usage statistics
    - Admin dashboard APIs
    """,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.APP_VERSION}


# API info endpoint
@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(servers_router, prefix="/api")
app.include_router(user_router, prefix="/api")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
