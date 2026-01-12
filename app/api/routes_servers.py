"""Server API routes for users."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, Server, ConnectionLog
from .schemas import ServerResponse, ConnectionCreate, ConnectionUpdate, ConnectionResponse
from .auth import get_current_user
from ..database.models import User

router = APIRouter(prefix="/servers", tags=["Servers"])


@router.get("", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    country: Optional[str] = None,
    protocol: Optional[str] = None
):
    """List available servers for connection."""
    query = select(Server).where(Server.is_active == True)
    
    # Filter premium servers for non-premium users
    if current_user.role not in ["admin", "premium"]:
        query = query.where(Server.is_premium == False)
    
    if country:
        query = query.where(Server.country_code == country)
    if protocol:
        query = query.where(Server.protocol == protocol)
    
    query = query.order_by(Server.country, Server.name)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/best", response_model=ServerResponse)
async def get_best_server(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    protocol: Optional[str] = None
):
    """Auto-select the best server based on load and latency."""
    query = select(Server).where(
        and_(
            Server.is_active == True,
            Server.current_users < Server.max_users
        )
    )
    
    if current_user.role not in ["admin", "premium"]:
        query = query.where(Server.is_premium == False)
    
    if protocol:
        query = query.where(Server.protocol == protocol)
    
    # Order by load (ascending) and latency (ascending)
    query = query.order_by(Server.current_load, Server.latency_ms)
    
    result = await db.execute(query.limit(1))
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No available servers"
        )
    
    return server


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get server details for connection."""
    result = await db.execute(
        select(Server).where(
            and_(
                Server.id == server_id,
                Server.is_active == True
            )
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check premium access
    if server.is_premium and current_user.role not in ["admin", "premium"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium server requires premium subscription"
        )
    
    return server


@router.get("/{server_id}/connect")
async def get_connection_info(
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get full server connection details including credentials."""
    result = await db.execute(
        select(Server).where(
            and_(
                Server.id == server_id,
                Server.is_active == True
            )
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check premium access
    if server.is_premium and current_user.role not in ["admin", "premium"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium server requires premium subscription"
        )
    
    # Check data limit
    if current_user.data_limit_mb:
        used_mb = (current_user.total_uploaded + current_user.total_downloaded) / (1024 * 1024)
        if used_mb >= current_user.data_limit_mb:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Data limit exceeded"
            )
    
    return {
        "server_id": str(server.id),
        "name": server.name,
        "host": server.host,
        "port": server.port,
        "protocol": server.protocol,
        "ssh_port": server.ssh_port,
        "ssl_port": server.ssl_port,
        "udp_port": server.udp_port,
        "username": server.username,
        "password": server.password,
        "sni_host": server.sni_host,
        "ssl_payload": server.ssl_payload,
        "country": server.country,
        "country_code": server.country_code
    }


@router.post("/connect", response_model=ConnectionResponse)
async def connect_to_server(
    connection: ConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a new connection."""
    # Verify server exists
    result = await db.execute(
        select(Server).where(Server.id == connection.server_id)
    )
    server = result.scalar_one_or_none()
    
    if not server or not server.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found or unavailable"
        )
    
    # Check max connections
    active_connections = await db.scalar(
        select(func.count(ConnectionLog.id)).where(
            and_(
                ConnectionLog.user_id == current_user.id,
                ConnectionLog.status == "connected"
            )
        )
    )
    
    if active_connections >= current_user.max_devices:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Maximum {current_user.max_devices} simultaneous connections allowed"
        )
    
    # Create connection log
    new_connection = ConnectionLog(
        user_id=current_user.id,
        server_id=server.id,
        protocol=connection.protocol.value,
        device_info=connection.device_info,
        status="connected",
        connected_at=datetime.utcnow()
    )
    
    db.add(new_connection)
    
    # Update server users count
    server.current_users += 1
    
    # Update user last connection
    current_user.last_connection = datetime.utcnow()
    
    await db.commit()
    await db.refresh(new_connection)
    
    return new_connection


@router.post("/disconnect/{connection_id}", response_model=ConnectionResponse)
async def disconnect(
    connection_id: UUID,
    data: ConnectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End a connection and record usage."""
    result = await db.execute(
        select(ConnectionLog).where(
            and_(
                ConnectionLog.id == connection_id,
                ConnectionLog.user_id == current_user.id
            )
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    # Update connection
    connection.bytes_uploaded = data.bytes_uploaded
    connection.bytes_downloaded = data.bytes_downloaded
    connection.status = "disconnected"
    connection.disconnected_at = datetime.utcnow()
    
    if connection.connected_at:
        connection.duration_seconds = int(
            (datetime.utcnow() - connection.connected_at).total_seconds()
        )
    
    # Update user stats
    current_user.total_uploaded += data.bytes_uploaded
    current_user.total_downloaded += data.bytes_downloaded
    
    # Update server users count
    if connection.server_id:
        server_result = await db.execute(
            select(Server).where(Server.id == connection.server_id)
        )
        server = server_result.scalar_one_or_none()
        if server and server.current_users > 0:
            server.current_users -= 1
    
    await db.commit()
    await db.refresh(connection)
    
    return connection


@router.get("/countries", response_model=List[dict])
async def get_server_countries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of available server countries."""
    query = select(
        Server.country,
        Server.country_code,
        func.count(Server.id)
    ).where(
        Server.is_active == True
    )
    
    if current_user.role not in ["admin", "premium"]:
        query = query.where(Server.is_premium == False)
    
    query = query.group_by(Server.country, Server.country_code)
    
    result = await db.execute(query)
    
    countries = []
    for row in result:
        countries.append({
            "country": row[0],
            "country_code": row[1],
            "server_count": row[2]
        })
    
    return countries
