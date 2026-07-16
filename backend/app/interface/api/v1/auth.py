from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.application.ports.token_service import AccessTokenPayload
from app.application.use_cases.auth.login import LoginCommand, LoginUseCase
from app.application.use_cases.auth.logout import LogoutCommand, LogoutUseCase
from app.application.use_cases.auth.refresh_access_token import (
    RefreshAccessTokenCommand,
    RefreshAccessTokenUseCase,
)
from app.application.use_cases.auth.register_user import RegisterUserCommand, RegisterUserUseCase
from app.domain.entities.user import User
from app.interface.api.deps import (
    get_current_access_token_payload,
    get_current_user,
    get_login_use_case,
    get_logout_use_case,
    get_refresh_access_token_use_case,
    get_register_user_use_case,
)
from app.interface.api.mappers import user_to_response
from app.interface.api.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.interface.api.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
) -> RegisterResponse:
    result = await use_case.execute(
        RegisterUserCommand(
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
        )
    )
    return RegisterResponse(id=result.user_id, email=result.email)


@router.post("/login", response_model=TokenResponse, summary="Exchange credentials for tokens")
async def login(
    body: LoginRequest,
    request: Request,
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> TokenResponse:
    user_agent, ip_address = _client_context(request)
    result = await use_case.execute(
        LoginCommand(
            email=body.email, password=body.password, user_agent=user_agent, ip_address=ip_address
        )
    )
    return TokenResponse(
        access_token=result.access_token,
        access_token_expires_at=result.access_token_expires_at,
        refresh_token=result.refresh_token,
        refresh_token_expires_at=result.refresh_token_expires_at,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Rotate an access/refresh token pair")
async def refresh(
    body: RefreshRequest,
    request: Request,
    use_case: RefreshAccessTokenUseCase = Depends(get_refresh_access_token_use_case),
) -> TokenResponse:
    user_agent, ip_address = _client_context(request)
    result = await use_case.execute(
        RefreshAccessTokenCommand(
            raw_refresh_token=body.refresh_token, user_agent=user_agent, ip_address=ip_address
        )
    )
    return TokenResponse(
        access_token=result.access_token,
        access_token_expires_at=result.access_token_expires_at,
        refresh_token=result.refresh_token,
        refresh_token_expires_at=result.refresh_token_expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Revoke the current session",
)
async def logout(
    body: LogoutRequest,
    payload: AccessTokenPayload = Depends(get_current_access_token_payload),
    use_case: LogoutUseCase = Depends(get_logout_use_case),
) -> None:
    await use_case.execute(
        LogoutCommand(
            raw_refresh_token=body.refresh_token,
            access_token_jti=payload.jti,
            access_token_expires_at=payload.expires_at,
        )
    )


@router.get("/me", response_model=UserResponse, summary="The authenticated user's profile")
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_to_response(current_user)
