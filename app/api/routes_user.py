"""User profile and config API routes."""
from datetime import datetime, date, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, User, Config, ConnectionLog, UsageStats
from .schemas import (
    UserResponse, UserUpdate, 
    ConfigCreate, ConfigResponse,
    UsageStatsResponse, UsageSummary,
    ConnectionResponse
)
from .auth import get_current_user, hash_password

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile."""
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile."""
    update_data = data.model_dump(exclude_unset=True)
    
    # Users can only update certain fields
    allowed_fields = ["email", "password"]
    update_data = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))
    
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.get("/usage", response_model=UsageSummary)
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365)
):
    """Get user usage summary."""
    start_date = date.today() - timedelta(days=days)
    
    result = await db.execute(
        select(
            func.sum(UsageStats.bytes_uploaded),
            func.sum(UsageStats.bytes_downloaded),
            func.sum(UsageStats.connection_count),
            func.sum(UsageStats.connection_time_seconds)
        ).where(
            and_(
                UsageStats.user_id == current_user.id,
                UsageStats.date >= start_date
            )
        )
    )
    row = result.one()
    
    return UsageSummary(
        total_uploaded=row[0] or 0,
        total_downloaded=row[1] or 0,
        total_connections=row[2] or 0,
        total_time_seconds=row[3] or 0,
        period_start=start_date,
        period_end=date.today()
    )


@router.get("/usage/daily", response_model=List[UsageStatsResponse])
async def get_daily_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365)
):
    """Get daily usage breakdown."""
    start_date = date.today() - timedelta(days=days)
    
    result = await db.execute(
        select(UsageStats).where(
            and_(
                UsageStats.user_id == current_user.id,
                UsageStats.date >= start_date
            )
        ).order_by(desc(UsageStats.date))
    )
    
    return result.scalars().all()


@router.get("/connections", response_model=List[ConnectionResponse])
async def get_connection_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100)
):
    """Get user connection history."""
    result = await db.execute(
        select(ConnectionLog).where(
            ConnectionLog.user_id == current_user.id
        ).order_by(desc(ConnectionLog.connected_at)).limit(limit)
    )
    
    return result.scalars().all()


@router.get("/data-remaining")
async def get_data_remaining(
    current_user: User = Depends(get_current_user)
):
    """Get remaining data allowance if limit is set."""
    if not current_user.data_limit_mb:
        return {
            "has_limit": False,
            "limit_mb": None,
            "used_mb": (current_user.total_uploaded + current_user.total_downloaded) / (1024 * 1024),
            "remaining_mb": None
        }
    
    used_mb = (current_user.total_uploaded + current_user.total_downloaded) / (1024 * 1024)
    remaining_mb = max(0, current_user.data_limit_mb - used_mb)
    
    return {
        "has_limit": True,
        "limit_mb": current_user.data_limit_mb,
        "used_mb": used_mb,
        "remaining_mb": remaining_mb,
        "percentage_used": (used_mb / current_user.data_limit_mb) * 100
    }


# ============ Configs ============

@router.get("/configs", response_model=List[ConfigResponse])
async def list_user_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's saved configs and public configs."""
    result = await db.execute(
        select(Config).where(
            and_(
                Config.is_active == True,
                (Config.created_by == current_user.id) | (Config.is_public == True)
            )
        ).order_by(desc(Config.created_at))
    )
    
    return result.scalars().all()


@router.post("/configs", response_model=ConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: ConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new configuration."""
    new_config = Config(
        name=config_data.name,
        protocol=config_data.protocol.value,
        payload=config_data.payload,
        server_host=config_data.server_host,
        server_port=config_data.server_port,
        ssh_host=config_data.ssh_host,
        ssh_port=config_data.ssh_port,
        ssh_username=config_data.ssh_username,
        ssh_password=config_data.ssh_password,
        sni_host=config_data.sni_host,
        ssl_enabled=config_data.ssl_enabled,
        proxy_host=config_data.proxy_host,
        proxy_port=config_data.proxy_port,
        custom_dns=config_data.custom_dns,
        dns_over_https=config_data.dns_over_https,
        is_public=False,  # Users cannot create public configs
        created_by=current_user.id
    )
    
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    
    return new_config


@router.get("/configs/{config_id}", response_model=ConfigResponse)
async def get_config(
    config_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific configuration."""
    result = await db.execute(
        select(Config).where(
            and_(
                Config.id == config_id,
                (Config.created_by == current_user.id) | (Config.is_public == True)
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )
    
    return config


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user's configuration."""
    result = await db.execute(
        select(Config).where(
            and_(
                Config.id == config_id,
                Config.created_by == current_user.id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found or not owned by user"
        )
    
    await db.delete(config)
    await db.commit()
    
    return {"message": "Config deleted successfully"}


@router.post("/configs/import")
async def import_config_from_url(
    url: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import configuration from a URL."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            config_data = response.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch config: {str(e)}"
        )
    
    # Parse and create config
    new_config = Config(
        name=config_data.get("name", "Imported Config"),
        protocol=config_data.get("protocol", "http_inject"),
        payload=config_data.get("payload"),
        server_host=config_data.get("server_host"),
        server_port=config_data.get("server_port"),
        ssh_host=config_data.get("ssh_host"),
        ssh_port=config_data.get("ssh_port"),
        sni_host=config_data.get("sni_host"),
        ssl_enabled=config_data.get("ssl_enabled", False),
        is_public=False,
        created_by=current_user.id
    )
    
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    
    return {"message": "Config imported successfully", "config_id": str(new_config.id)}
