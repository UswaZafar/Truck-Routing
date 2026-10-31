"""API error types and a handler that gives every error the same JSON shape.

Validation errors keep DRF's `{field: [messages]}` shape (the frontend maps them onto inputs); every other
error becomes `{"detail": str, "code": str}`.
"""

import logging

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class UpstreamError(APIException):
    """A third-party provider (routing, geocoding, weather) failed or is rate limiting us."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "An external data provider is unavailable. Please try again."
    default_code = "upstream_error"

    def __init__(self, detail=None, status_code: int | None = None):
        super().__init__(detail)
        if status_code is not None:
            self.status_code = status_code


class NoRouteError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "No drivable route was found between these places."
    default_code = "no_route"


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = NotFound()
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"detail": "Unexpected server error.", "code": "server_error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(exc, APIException) and isinstance(response.data, dict) and "detail" in response.data:
        codes = exc.get_codes()
        response.data["code"] = codes if isinstance(codes, str) else exc.default_code
    return response
