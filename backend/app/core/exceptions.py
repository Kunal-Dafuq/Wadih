import uuid
from typing import Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class WadihAPIException(Exception):
    """Base exception for all Wadih domain errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class UnauthenticatedException(WadihAPIException):
    def __init__(self, message: str = "Authentication required or invalid credentials."):
        super().__init__(
            code="UNAUTHENTICATED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(WadihAPIException):
    def __init__(self, message: str = "You do not have permission to access this resource."):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundException(WadihAPIException):
    def __init__(self, message: str = "The requested resource was not found."):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConsentRequiredException(WadihAPIException):
    def __init__(
        self,
        message: str = "This information is not available with the current permissions. Consent grant is required.",
    ):
        super().__init__(
            code="CONSENT_REQUIRED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NeedsClinicianReviewException(WadihAPIException):
    def __init__(
        self,
        message: str = "This finding requires genetic counsellor review before disclosure.",
    ):
        super().__init__(
            code="NEEDS_CLINICIAN_REVIEW",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationException(WadihAPIException):
    def __init__(self, message: str = "Provided request data failed validation."):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def format_error_response(
    code: str,
    message: str,
    request: Optional[Request] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if request else None
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


async def wadih_exception_handler(request: Request, exc: WadihAPIException) -> JSONResponse:
    return format_error_response(
        code=exc.code,
        message=exc.message,
        request=request,
        status_code=exc.status_code,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    message = str(exc.detail) if exc.detail else "An error occurred."
    return format_error_response(
        code=code,
        message=message,
        request=request,
        status_code=exc.status_code,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Summarize validation errors safely
    error_msgs = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        error_msgs.append(f"{loc}: {msg}")
    message = "; ".join(error_msgs) if error_msgs else "Provided request data failed validation."
    return format_error_response(
        code="VALIDATION_ERROR",
        message=message,
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return format_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected internal server error occurred.",
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
