"""Login, session lookup, and logout endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.auth import AuthUser, get_auth_service, get_current_user
from app.core.config import get_settings
from app.schemas.auth import LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=UserResponse)
async def login(request: LoginRequest) -> JSONResponse:
    """Authenticate one of the three configured users and set a session cookie."""
    auth_service = get_auth_service()
    user = auth_service.authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid username or password.",
                }
            },
        )

    settings = get_settings()
    token = await auth_service.create_session(user.username)
    response = JSONResponse({"username": user.username})
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_hours * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=UserResponse)
async def me(current_user: AuthUser = Depends(get_current_user)) -> UserResponse:
    """Return the account attached to the current session."""
    return UserResponse(username=current_user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> Response:
    """Invalidate the current session and remove its browser cookie."""
    settings = get_settings()
    await get_auth_service().delete_session(request.cookies.get(settings.auth_cookie_name))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response
