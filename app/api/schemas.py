"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from enum import Enum


# ============ Enums ============

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"


class Protocol(str, Enum):
    HTTP_INJECT = "http_inject"
    SSH_DIRECT = "ssh_direct"
    SSH_SSL = "ssh_ssl"
    SSH_UDP = "ssh_udp"
    SSL_TLS = "ssl_tls"
    V2RAY_VMESS = "v2ray_vmess"
    V2RAY_VLESS = "v2ray_vless"
    SHADOWSOCKS = "shadowsocks"
    TROJAN = "trojan"
    WIREGUARD = "wireguard"
    OPENVPN = "openvpn"


# ============ Auth Schemas ============

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    refresh_token: str


# ============ User Schemas ============

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_locked: bool = False
    max_devices: int = 1
    data_limit_mb: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_locked: Optional[bool] = None
    role: Optional[UserRole] = None
    max_devices: Optional[int] = None
    data_limit_mb: Optional[int] = None
    expiry_date: Optional[datetime] = None


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    is_locked: bool
    max_devices: int
    data_limit_mb: Optional[int]
    total_uploaded: int
    total_downloaded: int
    last_login: Optional[datetime]
    last_connection: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWithStats(UserResponse):
    """User with additional statistics."""
    current_connections: int = 0
    today_usage_mb: float = 0.0
    is_online: bool = False


# ============ Server Schemas ============

class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str
    port: int = Field(..., ge=1, le=65535)
    protocol: Protocol
    
    ssh_port: Optional[int] = None
    ssl_port: Optional[int] = None
    udp_port: Optional[int] = None
    
    country: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    
    username: Optional[str] = None
    password: Optional[str] = None
    
    is_premium: bool = False
    max_users: int = 100
    
    sni_host: Optional[str] = None
    ssl_payload: Optional[str] = None


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[Protocol] = None
    
    ssh_port: Optional[int] = None
    ssl_port: Optional[int] = None
    udp_port: Optional[int] = None
    
    country: Optional[str] = None
    country_code: Optional[str] = None
    
    username: Optional[str] = None
    password: Optional[str] = None
    
    is_active: Optional[bool] = None
    is_premium: Optional[bool] = None
    max_users: Optional[int] = None
    
    sni_host: Optional[str] = None
    ssl_payload: Optional[str] = None


class ServerResponse(BaseModel):
    id: UUID
    name: str
    host: str
    port: int
    protocol: str
    
    ssh_port: Optional[int]
    ssl_port: Optional[int]
    udp_port: Optional[int]
    
    country: Optional[str]
    country_code: Optional[str]
    city: Optional[str]
    
    is_active: bool
    is_premium: bool
    max_users: int
    current_users: int
    current_load: float
    
    latency_ms: Optional[int]
    bandwidth_mbps: Optional[float]
    
    sni_host: Optional[str]
    
    created_at: datetime
    last_check: Optional[datetime]
    
    class Config:
        from_attributes = True


class ServerWithCredentials(ServerResponse):
    """Server response including credentials for connection."""
    username: Optional[str]
    password: Optional[str]
    ssl_payload: Optional[str]


# ============ Connection Schemas ============

class ConnectionCreate(BaseModel):
    server_id: UUID
    protocol: Protocol
    device_info: Optional[str] = None


class ConnectionUpdate(BaseModel):
    bytes_uploaded: int = 0
    bytes_downloaded: int = 0
    status: str = "connected"
    disconnect_reason: Optional[str] = None


class ConnectionResponse(BaseModel):
    id: UUID
    user_id: UUID
    server_id: Optional[UUID]
    protocol: str
    client_ip: Optional[str]
    device_info: Optional[str]
    bytes_uploaded: int
    bytes_downloaded: int
    status: str
    connected_at: datetime
    disconnected_at: Optional[datetime]
    duration_seconds: Optional[int]
    
    class Config:
        from_attributes = True


class ConnectionWithDetails(ConnectionResponse):
    """Connection with user and server details."""
    username: str
    server_name: Optional[str]
    server_country: Optional[str]


# ============ Usage Stats Schemas ============

class UsageStatsResponse(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    protocol: Optional[str]
    bytes_uploaded: int
    bytes_downloaded: int
    connection_count: int
    connection_time_seconds: int
    
    class Config:
        from_attributes = True


class UsageSummary(BaseModel):
    """Aggregated usage summary."""
    total_uploaded: int
    total_downloaded: int
    total_connections: int
    total_time_seconds: int
    period_start: date
    period_end: date


# ============ Config Schemas ============

class ConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    protocol: Protocol
    payload: Optional[str] = None
    
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    
    sni_host: Optional[str] = None
    ssl_enabled: bool = False
    
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    
    custom_dns: Optional[str] = None
    dns_over_https: bool = False
    
    is_public: bool = False


class ConfigCreate(ConfigBase):
    pass


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    protocol: Optional[Protocol] = None
    payload: Optional[str] = None
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class ConfigResponse(BaseModel):
    id: UUID
    name: str
    protocol: str
    payload: Optional[str]
    server_host: Optional[str]
    server_port: Optional[int]
    sni_host: Optional[str]
    ssl_enabled: bool
    is_public: bool
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Admin Dashboard Schemas ============

class DashboardStats(BaseModel):
    """Admin dashboard statistics."""
    total_users: int
    active_users: int
    premium_users: int
    total_servers: int
    active_servers: int
    
    current_connections: int
    today_connections: int
    
    today_upload_bytes: int
    today_download_bytes: int
    total_upload_bytes: int
    total_download_bytes: int
    
    protocol_usage: dict  # Protocol -> connection count
    country_usage: dict   # Country -> connection count


class ServerStatsResponse(BaseModel):
    """Real-time server statistics."""
    server_id: UUID
    server_name: str
    active_connections: int
    cpu_usage: float
    memory_usage: float
    bandwidth_in: int
    bandwidth_out: int
    latency_ms: Optional[int]
    timestamp: datetime


# ============ Pagination ============

class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: List
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
