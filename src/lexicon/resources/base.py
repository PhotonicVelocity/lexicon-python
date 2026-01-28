"""Base resource helpers."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..client import Lexicon


class Resource:
    """Shared helpers for resource classes."""

    def __init__(self, client: "Lexicon") -> None:
        self._client = client

    @property
    def _logger(self):
        return self._client._logger

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any] | list[tuple[str, Any]]] = None,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        return self._client.request(method, path, params=params, json=json, timeout=timeout)

    def _get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any] | list[tuple[str, Any]]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        return self._request("GET", path, params=params, timeout=timeout)

    def _post(
        self,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        return self._request("POST", path, json=json, timeout=timeout)

    def _patch(
        self,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        return self._request("PATCH", path, json=json, timeout=timeout)

    def _delete(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any] | list[tuple[str, Any]]] = None,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        return self._request("DELETE", path, params=params, json=json, timeout=timeout)
