"""Admin API routes for complete control panel."""
from datetime import datetime, date, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db, User, Server, ConnectionLog, UsageStats, Config
from .schemas import (
    UserCreate, UserUpdate, UserResponse, UserWithStats,
    ServerCreate, ServerUpdate, ServerResponse, ServerWithCredentials,
    ConnectionResponse, ConnectionWithDetails,
    UsageStatsResponse, UsageSummary,
    ConfigCreate, ConfigUpdate, ConfigResponse,
    DashboardStats, ServerStatsResponse,
    PaginatedResponse
)
from .auth import get_admin_user, hash_password, generate_user_key

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============ Dashboard ============

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics."""
    today = date.today()
    
    # User counts
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )
    premium_users = await db.scalar(
        select(func.count(User.id)).where(User.role == "premium")
    )
    
    # Server counts
    total_servers = await db.scalar(select(func.count(Server.id)))
    active_servers = await db.scalar(
        select(func.count(Server.id)).where(Server.is_active == True)
    )
    
    # Current connections
    current_connections = await db.scalar(
        select(func.count(ConnectionLog.id)).where(
            ConnectionLog.status == "connected"
        )
    )
    
    # Today's connections
    today_start = datetime.combine(today, datetime.min.time())
    today_connections = await db.scalar(
        select(func.count(ConnectionLog.id)).where(
            ConnectionLog.connected_at >= today_start
        )
    )
    
    # Today's data usage
    today_stats = await db.execute(
        select(
            func.sum(UsageStats.bytes_uploaded),
            func.sum(UsageStats.bytes_downloaded)
        ).where(UsageStats.date == today)
    )
    today_row = today_stats.one()
    today_upload = today_row[0] or 0
    today_download = today_row[1] or 0
    
    # Total data usage
    total_stats = await db.execute(
        select(
            func.sum(User.total_uploaded),
            func.sum(User.total_downloaded)
        )
    )
    total_row = total_stats.one()
    total_upload = total_row[0] or 0
    total_download = total_row[1] or 0
    
    # Protocol usage (last 24h)
    protocol_result = await db.execute(
        select(
            ConnectionLog.protocol,
            func.count(ConnectionLog.id)
        ).where(
            ConnectionLog.connected_at >= datetime.utcnow() - timedelta(days=1)
        ).group_by(ConnectionLog.protocol)
    )
    protocol_usage = {row[0]: row[1] for row in protocol_result}
    
    # Country usage (from servers)
    country_result = await db.execute(
        select(
            Server.country_code,
            func.sum(Server.current_users)
        ).where(
            Server.is_active == True
        ).group_by(Server.country_code)
    )
    country_usage = {row[0] or "Unknown": row[1] or 0 for row in country_result}
    
    return DashboardStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        premium_users=premium_users or 0,
        total_servers=total_servers or 0,
        active_servers=active_servers or 0,
        current_connections=current_connections or 0,
        today_connections=today_connections or 0,
        today_upload_bytes=today_upload,
        today_download_bytes=today_download,
        total_upload_bytes=total_upload,
        total_download_bytes=total_download,
        protocol_usage=protocol_usage,
        country_usage=country_usage
    )


# ============ User Management ============

@router.get("/users", response_model=List[UserWithStats])
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """List all users with statistics."""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    # Order and paginate
    query = query.order_by(desc(User.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Get current connections for each user
    user_stats = []
    for user in users:
        # Current connections
        conn_count = await db.scalar(
            select(func.count(ConnectionLog.id)).where(
                and_(
                    ConnectionLog.user_id == user.id,
                    ConnectionLog.status == "connected"
                )
            )
        )
        
        # Today's usage
        today_usage = await db.execute(
            select(func.sum(UsageStats.bytes_uploaded + UsageStats.bytes_downloaded))
            .where(
                and_(
                    UsageStats.user_id == user.id,
                    UsageStats.date == date.today()
                )
            )
        )
        today_bytes = today_usage.scalar() or 0
        
        user_stats.append(UserWithStats(
            **UserResponse.model_validate(user).model_dump(),
            current_connections=conn_count or 0,
            today_usage_mb=today_bytes / (1024 * 1024),
            is_online=conn_count > 0
        ))
    
    return user_stats


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user."""
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email exists
    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=user_data.role.value,
        is_active=user_data.is_active,
        is_locked=user_data.is_locked,
        max_devices=user_data.max_devices,
        data_limit_mb=user_data.data_limit_mb
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.get("/users/{user_id}", response_model=UserWithStats)
async def get_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user details with statistics."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get current connections
    conn_count = await db.scalar(
        select(func.count(ConnectionLog.id)).where(
            and_(
                ConnectionLog.user_id == user.id,
                ConnectionLog.status == "connected"
            )
        )
    )
    
    # Today's usage
    today_usage = await db.execute(
        select(func.sum(UsageStats.bytes_uploaded + UsageStats.bytes_downloaded))
        .where(
            and_(
                UsageStats.user_id == user.id,
                UsageStats.date == date.today()
            )
        )
    )
    today_bytes = today_usage.scalar() or 0
    
    return UserWithStats(
        **UserResponse.model_validate(user).model_dump(),
        current_connections=conn_count or 0,
        today_usage_mb=today_bytes / (1024 * 1024),
        is_online=conn_count > 0
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user details."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)
    
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))
    
    if "role" in update_data:
        update_data["role"] = update_data["role"].value
    
    for key, value in update_data.items():
        setattr(user, key, value)
    
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin user"
        )
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted successfully"}


@router.post("/users/{user_id}/lock")
async def lock_user_device(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Lock user to their current device."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_locked = True
    await db.commit()
    
    return {"message": "User device locked", "device_id": user.device_id}


@router.post("/users/{user_id}/unlock")
async def unlock_user_device(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Unlock user from device restriction."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_locked = False
    user.device_id = None
    await db.commit()
    
    return {"message": "User device unlocked"}


@router.post("/users/{user_id}/disconnect")
async def disconnect_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Force disconnect all user connections."""
    # Update all active connections
    result = await db.execute(
        select(ConnectionLog).where(
            and_(
                ConnectionLog.user_id == user_id,
                ConnectionLog.status == "connected"
            )
        )
    )
    connections = result.scalars().all()
    
    for conn in connections:
        conn.status = "disconnected"
        conn.disconnected_at = datetime.utcnow()
        conn.disconnect_reason = "Admin force disconnect"
        if conn.connected_at:
            conn.duration_seconds = int(
                (datetime.utcnow() - conn.connected_at).total_seconds()
            )
    
    await db.commit()
    
    return {"message": f"Disconnected {len(connections)} connections"}


@router.post("/users/generate-key")
async def generate_user_access_key(
    admin: User = Depends(get_admin_user)
):
    """Generate a random user access key."""
    return {"key": generate_user_key(16)}


# ============ User Usage Statistics ============

@router.get("/users/{user_id}/usage", response_model=List[UsageStatsResponse])
async def get_user_usage(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365)
):
    """Get user usage statistics for the specified period."""
    start_date = date.today() - timedelta(days=days)
    
    result = await db.execute(
        select(UsageStats).where(
            and_(
                UsageStats.user_id == user_id,
                UsageStats.date >= start_date
            )
        ).order_by(desc(UsageStats.date))
    )
    
    return result.scalars().all()


@router.get("/users/{user_id}/connections", response_model=List[ConnectionResponse])
async def get_user_connections(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100)
):
    """Get user connection history."""
    result = await db.execute(
        select(ConnectionLog).where(
            ConnectionLog.user_id == user_id
        ).order_by(desc(ConnectionLog.connected_at)).limit(limit)
    )
    
    return result.scalars().all()


# ============ Server Management ============

@router.get("/servers", response_model=List[ServerResponse])
async def list_servers(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    country: Optional[str] = None,
    protocol: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """List all servers with current status."""
    query = select(Server)
    
    if country:
        query = query.where(Server.country_code == country)
    if protocol:
        query = query.where(Server.protocol == protocol)
    if is_active is not None:
        query = query.where(Server.is_active == is_active)
    
    query = query.order_by(Server.country, Server.name)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/servers", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    server_data: ServerCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a new server."""
    new_server = Server(
        name=server_data.name,
        host=server_data.host,
        port=server_data.port,
        protocol=server_data.protocol.value,
        ssh_port=server_data.ssh_port,
        ssl_port=server_data.ssl_port,
        udp_port=server_data.udp_port,
        country=server_data.country,
        country_code=server_data.country_code,
        city=server_data.city,
        username=server_data.username,
        password=server_data.password,
        is_premium=server_data.is_premium,
        max_users=server_data.max_users,
        sni_host=server_data.sni_host,
        ssl_payload=server_data.ssl_payload
    )
    
    db.add(new_server)
    await db.commit()
    await db.refresh(new_server)
    
    return new_server


@router.get("/servers/{server_id}", response_model=ServerWithCredentials)
async def get_server(
    server_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get server details including credentials."""
    result = await db.execute(
        select(Server).where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    return server


@router.put("/servers/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: UUID,
    server_data: ServerUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update server details."""
    result = await db.execute(
        select(Server).where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    update_data = server_data.model_dump(exclude_unset=True)
    
    if "protocol" in update_data:
        update_data["protocol"] = update_data["protocol"].value
    
    for key, value in update_data.items():
        setattr(server, key, value)
    
    server.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(server)
    
    return server


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a server."""
    result = await db.execute(
        select(Server).where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    await db.delete(server)
    await db.commit()
    
    return {"message": "Server deleted successfully"}


@router.get("/servers/{server_id}/stats", response_model=ServerStatsResponse)
async def get_server_stats(
    server_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get real-time server statistics."""
    result = await db.execute(
        select(Server).where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Get active connections
    active_conns = await db.scalar(
        select(func.count(ConnectionLog.id)).where(
            and_(
                ConnectionLog.server_id == server_id,
                ConnectionLog.status == "connected"
            )
        )
    )
    
    # Get bandwidth (last hour)
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    bandwidth = await db.execute(
        select(
            func.sum(ConnectionLog.bytes_uploaded),
            func.sum(ConnectionLog.bytes_downloaded)
        ).where(
            and_(
                ConnectionLog.server_id == server_id,
                ConnectionLog.connected_at >= hour_ago
            )
        )
    )
    bw_row = bandwidth.one()
    
    return ServerStatsResponse(
        server_id=server.id,
        server_name=server.name,
        active_connections=active_conns or 0,
        cpu_usage=server.current_load,
        memory_usage=0.0,  # Would require agent on server
        bandwidth_in=bw_row[0] or 0,
        bandwidth_out=bw_row[1] or 0,
        latency_ms=server.latency_ms,
        timestamp=datetime.utcnow()
    )


# ============ Live Connections ============

@router.get("/connections", response_model=List[ConnectionWithDetails])
async def get_live_connections(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    server_id: Optional[UUID] = None,
    protocol: Optional[str] = None
):
    """Get all active connections with details."""
    query = select(ConnectionLog, User.username, Server.name, Server.country_code).join(
        User, ConnectionLog.user_id == User.id
    ).outerjoin(
        Server, ConnectionLog.server_id == Server.id
    ).where(
        ConnectionLog.status == "connected"
    )
    
    if server_id:
        query = query.where(ConnectionLog.server_id == server_id)
    if protocol:
        query = query.where(ConnectionLog.protocol == protocol)
    
    query = query.order_by(desc(ConnectionLog.connected_at))
    
    result = await db.execute(query)
    rows = result.all()
    
    connections = []
    for row in rows:
        conn, username, server_name, country = row
        connections.append(ConnectionWithDetails(
            **ConnectionResponse.model_validate(conn).model_dump(),
            username=username,
            server_name=server_name,
            server_country=country
        ))
    
    return connections


# ============ Overall Statistics ============

@router.get("/stats/usage")
async def get_usage_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=90)
):
    """Get overall usage statistics for the specified period."""
    start_date = date.today() - timedelta(days=days)
    
    # Daily totals
    daily_result = await db.execute(
        select(
            UsageStats.date,
            func.sum(UsageStats.bytes_uploaded),
            func.sum(UsageStats.bytes_downloaded),
            func.sum(UsageStats.connection_count)
        ).where(
            UsageStats.date >= start_date
        ).group_by(UsageStats.date).order_by(UsageStats.date)
    )
    
    daily_data = []
    for row in daily_result:
        daily_data.append({
            "date": row[0].isoformat(),
            "uploaded": row[1] or 0,
            "downloaded": row[2] or 0,
            "connections": row[3] or 0
        })
    
    # Protocol breakdown
    protocol_result = await db.execute(
        select(
            UsageStats.protocol,
            func.sum(UsageStats.bytes_uploaded + UsageStats.bytes_downloaded),
            func.sum(UsageStats.connection_count)
        ).where(
            UsageStats.date >= start_date
        ).group_by(UsageStats.protocol)
    )
    
    protocol_data = {}
    for row in protocol_result:
        if row[0]:
            protocol_data[row[0]] = {
                "bytes": row[1] or 0,
                "connections": row[2] or 0
            }
    
    return {
        "daily": daily_data,
        "by_protocol": protocol_data,
        "period_days": days
    }


# ============ Config Management ============

@router.get("/configs", response_model=List[ConfigResponse])
async def list_configs(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    is_public: Optional[bool] = None
):
    """List all configurations."""
    query = select(Config)
    
    if is_public is not None:
        query = query.where(Config.is_public == is_public)
    
    query = query.order_by(desc(Config.created_at))
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/configs", response_model=ConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: ConfigCreate,
    admin: User = Depends(get_admin_user),
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
        is_public=config_data.is_public,
        created_by=admin.id
    )
    
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    
    return new_config


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a configuration."""
    result = await db.execute(
        select(Config).where(Config.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Config not found"
        )
    
    await db.delete(config)
    await db.commit()
    
    return {"message": "Config deleted successfully"}
