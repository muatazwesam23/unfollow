"""Authentication API routes."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, User
from .schemas import (
    UserRegister, UserLogin, TokenResponse, TokenRefresh, UserResponse
)
from .auth import (
    hash_password, verify_password, create_access_token, 
    create_refresh_token, decode_token, get_current_user
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account."""
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists (if provided)
    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="user"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Generate tokens
    token_data = {"sub": str(new_user.id), "username": new_user.username}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login with username and password."""
    # Find user
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    if user.is_locked:
        # Check device lock
        if user.device_id and user_data.device_id:
            if user.device_id != user_data.device_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is locked to another device"
                )
    
    # Update device info and last login
    if user_data.device_id:
        user.device_id = user_data.device_id
    if user_data.device_name:
        user.device_name = user_data.device_name
    user.last_login = datetime.utcnow()
    
    await db.commit()
    
    # Generate tokens
    token_data = {"sub": str(user.id), "username": user.username, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    payload = decode_token(data.refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user_id = payload.get("sub")
    
    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )
    
    # Generate new tokens
    token_data = {"sub": str(user.id), "username": user.username, "role": user.role}
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Get current user information."""
    return current_user


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """Logout current user (invalidate tokens on client side)."""
    # In a more robust implementation, you would blacklist the token
    return {"message": "Successfully logged out"}
