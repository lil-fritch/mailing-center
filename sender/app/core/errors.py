from typing import Optional, Dict, Any
from fastapi import HTTPException


class AppError(Exception):
    """
    Used for expected application errors that should be shown to the user.
    Do NOT use this for unexpected errors or server issues.
    """
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=400,
            detail={
                "message": self.message,
                "details": self.details
            }
        ) 