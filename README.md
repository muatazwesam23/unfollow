# VPN Tunnel Backend

## Overview
FastAPI backend for VPN Tunnel application with complete admin control, user management, and connection tracking.

## Features
- 🔐 JWT Authentication (access + refresh tokens)
- 👥 Complete user management (CRUD, lock/unlock, device binding)
- 🖥️ Server management with real-time statistics
- 📊 Connection tracking and usage analytics
- 🛡️ Role-based access control (admin, premium, user)
- 📈 Dashboard with comprehensive statistics

## Quick Start

### 1. Setup Environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Setup Database
Create PostgreSQL database:
```sql
CREATE DATABASE vpn_tunnel;
```

### 4. Run Server
```bash
uvicorn app.main:app --reload
```

Server will start at http://localhost:8000

## API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login
- `POST /api/auth/refresh` - Refresh token
- `GET /api/auth/me` - Current user info

### Admin (requires admin role)
- `GET /api/admin/dashboard` - Dashboard statistics
- `GET /api/admin/users` - List users
- `POST /api/admin/users` - Create user
- `PUT /api/admin/users/{id}` - Update user
- `DELETE /api/admin/users/{id}` - Delete user
- `POST /api/admin/users/{id}/lock` - Lock user device
- `POST /api/admin/users/{id}/disconnect` - Force disconnect
- `GET /api/admin/servers` - List servers
- `POST /api/admin/servers` - Add server
- `GET /api/admin/connections` - Live connections
- `GET /api/admin/stats/usage` - Usage statistics

### Servers
- `GET /api/servers` - List available servers
- `GET /api/servers/best` - Get best server
- `GET /api/servers/{id}/connect` - Get connection info
- `POST /api/servers/connect` - Register connection
- `POST /api/servers/disconnect/{id}` - End connection

### User
- `GET /api/user/profile` - Get profile
- `PUT /api/user/profile` - Update profile
- `GET /api/user/usage` - Usage summary
- `GET /api/user/configs` - List configs
- `POST /api/user/configs` - Create config

## Database Schema
- **users**: User accounts with roles, limits, and stats
- **servers**: VPN servers with protocols and credentials
- **connection_logs**: Connection history with usage
- **usage_stats**: Daily aggregated statistics
- **configs**: VPN configuration profiles

## Default Admin
- Username: `admin`
- Password: `admin123`

⚠️ **Change these in production!**
