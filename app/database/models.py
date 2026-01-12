"""SQLAlchemy database models."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime, 
    ForeignKey, Text, Date, Enum as SQLEnum, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from enum import Enum

from .database import Base


class UserRole(str, Enum):
    """User roles enumeration."""
    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"


class Protocol(str, Enum):
    """VPN Protocol types."""
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


class User(Base):
    """User model for authentication and management."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Device management
    device_id = Column(String(100), nullable=True)
    device_name = Column(String(100), nullable=True)
    max_devices = Column(Integer, default=1)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    role = Column(String(20), default=UserRole.USER.value)
    
    # Limits
    data_limit_mb = Column(BigInteger, nullable=True)  # NULL = unlimited
    expiry_date = Column(DateTime, nullable=True)
    
    # Stats
    total_uploaded = Column(BigInteger, default=0)
    total_downloaded = Column(BigInteger, default=0)
    last_login = Column(DateTime, nullable=True)
    last_connection = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    connections = relationship("ConnectionLog", back_populates="user", cascade="all, delete-orphan")
    usage_stats = relationship("UsageStats", back_populates="user", cascade="all, delete-orphan")
    configs = relationship("Config", back_populates="created_by_user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"


class Server(Base):
    """VPN Server model."""
    __tablename__ = "servers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    
    # Connection details
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    ssh_port = Column(Integer, nullable=True)
    ssl_port = Column(Integer, nullable=True)
    udp_port = Column(Integer, nullable=True)
    
    # Protocol support
    protocol = Column(String(50), nullable=False)
    supported_protocols = Column(Text, nullable=True)  # JSON array
    
    # Location
    country = Column(String(50), nullable=True)
    country_code = Column(String(5), nullable=True)
    city = Column(String(50), nullable=True)
    
    # Server credentials (for SSH/SSL)
    username = Column(String(100), nullable=True)
    password = Column(String(255), nullable=True)
    
    # Status and limits
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    max_users = Column(Integer, default=100)
    current_users = Column(Integer, default=0)
    current_load = Column(Float, default=0.0)  # Percentage
    
    # Performance
    latency_ms = Column(Integer, nullable=True)
    bandwidth_mbps = Column(Float, nullable=True)
    
    # SSL/TLS Config
    sni_host = Column(String(255), nullable=True)
    ssl_payload = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check = Column(DateTime, nullable=True)
    
    # Relationships
    connections = relationship("ConnectionLog", back_populates="server")
    
    def __repr__(self):
        return f"<Server {self.name} ({self.host})>"


class ConnectionLog(Base):
    """Connection history and logging."""
    __tablename__ = "connection_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="SET NULL"), nullable=True)
    
    # Connection info
    protocol = Column(String(50), nullable=False)
    client_ip = Column(String(50), nullable=True)
    device_info = Column(String(255), nullable=True)
    
    # Data usage
    bytes_uploaded = Column(BigInteger, default=0)
    bytes_downloaded = Column(BigInteger, default=0)
    
    # Status
    status = Column(String(20), default="connected")  # connected, disconnected, failed
    disconnect_reason = Column(String(255), nullable=True)
    
    # Timestamps
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="connections")
    server = relationship("Server", back_populates="connections")
    
    def __repr__(self):
        return f"<ConnectionLog {self.user_id} -> {self.server_id}>"


class UsageStats(Base):
    """Daily usage statistics per user."""
    __tablename__ = "usage_stats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Date and protocol
    date = Column(Date, nullable=False)
    protocol = Column(String(50), nullable=True)
    
    # Usage data
    bytes_uploaded = Column(BigInteger, default=0)
    bytes_downloaded = Column(BigInteger, default=0)
    connection_count = Column(Integer, default=0)
    connection_time_seconds = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="usage_stats")
    
    class Meta:
        unique_together = [("user_id", "date", "protocol")]
    
    def __repr__(self):
        return f"<UsageStats {self.user_id} {self.date}>"


class Config(Base):
    """VPN Configuration profiles."""
    __tablename__ = "configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    
    # Config details
    protocol = Column(String(50), nullable=False)
    payload = Column(Text, nullable=True)
    server_host = Column(String(255), nullable=True)
    server_port = Column(Integer, nullable=True)
    
    # SSH settings
    ssh_host = Column(String(255), nullable=True)
    ssh_port = Column(Integer, nullable=True)
    ssh_username = Column(String(100), nullable=True)
    ssh_password = Column(String(255), nullable=True)
    
    # SSL settings
    sni_host = Column(String(255), nullable=True)
    ssl_enabled = Column(Boolean, default=False)
    
    # Proxy settings
    proxy_host = Column(String(255), nullable=True)
    proxy_port = Column(Integer, nullable=True)
    
    # DNS settings
    custom_dns = Column(String(100), nullable=True)
    dns_over_https = Column(Boolean, default=False)
    
    # Advanced
    extra_config = Column(Text, nullable=True)  # JSON
    
    # Visibility
    is_public = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Ownership
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = relationship("User", back_populates="configs")
    
    def __repr__(self):
        return f"<Config {self.name}>"


class ServerStats(Base):
    """Real-time server statistics."""
    __tablename__ = "server_stats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    
    # Stats
    timestamp = Column(DateTime, default=datetime.utcnow)
    active_connections = Column(Integer, default=0)
    cpu_usage = Column(Float, default=0.0)
    memory_usage = Column(Float, default=0.0)
    bandwidth_in = Column(BigInteger, default=0)
    bandwidth_out = Column(BigInteger, default=0)
    latency_ms = Column(Integer, nullable=True)
    
    def __repr__(self):
        return f"<ServerStats {self.server_id} @ {self.timestamp}>"
