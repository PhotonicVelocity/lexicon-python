"""Custom tag resource wrapper."""

from __future__ import annotations

from typing import Optional, Sequence, TYPE_CHECKING, cast

from .base import Resource
from .tags_types import TagResponse
from ._common_types import ValidationMode, _normalize_id_sequence

if TYPE_CHECKING:  # pragma: no cover
    from .tag_categories import TagCategories


class Tags(Resource):
    """Custom tag operations."""

    categories: TagCategories

    def list(
        self,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TagResponse] | None:
        """Fetch all tags.

        Parameters
        ----------
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        list[TagResponse] or None
            List of tag dicts, or ``None`` on error.
        """
        response = self._get("/tags", timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        tags = data.get("tags") if isinstance(data, dict) else None
        if isinstance(tags, list):
            return tags
        self._logger.warning("Tags response missing expected tags list.")
        return None

    def add(
        self,
        category_id: int,
        label: str,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TagResponse | None:
        """Create a new custom tag.

        Parameters
        ----------
        category_id
            Tag category identifier.
        label
            Tag label.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        TagResponse or None
            Created tag dict, or ``None`` on error.
        """
        if not isinstance(category_id, int) or category_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid category_id: {category_id}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid category_id for add: %s", category_id)
                return None
        
        if not isinstance(label, str) or not label.strip():
            if validation == "strict":
                raise ValueError(f"Invalid label: {label}")
            if validation == "warn":
                self._logger.warning("Invalid label for add: %s", label)
            return None

        payload = {"categoryId": category_id, "label": label}
        response = self._post("/tag", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        # The OpenAPI spec says the created tag is in `data`, but the API directly returns tag objects.
        # Handle both cases until the spec or API is fixed.
        if isinstance(data, dict):
            # This is how the OpenAPI spec says it should be.
            return cast(TagResponse, data)
        if isinstance(response, dict) and "id" in response:
            # This is how the API actually behaves.
            return cast(TagResponse, response)
        self._logger.warning("Create tag response missing expected data. Response was %s", response)
        return None

    def update(
        self,
        tag_id: int,
        *,
        category_id: Optional[int] = None,
        label: Optional[str] = None,
        position: Optional[int] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TagResponse | None:
        """Update an existing custom tag.

        Parameters
        ----------
        tag_id
            Tag identifier.
        category_id
            New category identifier.
        label
            New tag label.
        position
            New position within the category.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        TagResponse or None
            Updated tag dict, or ``None`` on error.
        """
        if not isinstance(tag_id, int) or tag_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid tag_id: {tag_id}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid tag_id for update: %s", tag_id)
                return None
        
        if category_id is not None and (not isinstance(category_id, int) or category_id < 1):
            if validation == "strict":
                raise ValueError(f"Invalid category_id: {category_id}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid category_id for update: %s", category_id)
                return None
        
        if label is not None and (not isinstance(label, str) or not label.strip()):
            if validation == "strict":
                raise ValueError(f"Invalid label: {label}")
            if validation == "warn":
                self._logger.warning("Invalid label for update: %s", label)
            return None
        
        if position is not None and (not isinstance(position, int) or position < 0):
            if validation == "strict":
                raise ValueError(f"Invalid position: {position}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid position for update: %s", position)
                return None

        payload: dict[str, object] = {"id": tag_id}
        if category_id is not None:
            payload["categoryId"] = category_id
        if label is not None:
            payload["label"] = label
        if position is not None:
            payload["position"] = position

        if len(payload) == 1:
            self._logger.warning("No updates provided for tag %s", tag_id)
            return None

        response = self._patch("/tag", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        # The OpenAPI spec says the updated tag is in `data`, but the API directly returns tag objects.
        # Handle both cases until the spec or API is fixed.
        if isinstance(data, dict):
            # This is how the OpenAPI spec says it should be.
            return cast(TagResponse, data)
        if isinstance(response, dict) and "id" in response:
            # This is how the API actually behaves.
            return cast(TagResponse, response)
        self._logger.warning("Update tag response missing expected data.")
        return None

    def delete(
        self,
        tag_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Delete one or more custom tags by ID.

        Parameters
        ----------
        tag_ids
            Tag ID or iterable of tag identifiers.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        bool
            ``True`` when the delete request succeeds.
        """
        # When validation is off, pass input directly without transformation
        if validation == "off":
            ids = [tag_ids] if isinstance(tag_ids, int) else tag_ids
        else:
            # Normalize input to list of IDs with validation
            ids = _normalize_id_sequence(tag_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid tag_ids: {tag_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid tag_ids for delete: %s", tag_ids)
                    return False

        for tag_id in ids:
            response = self._delete("/tag", json={"id": tag_id}, timeout=timeout)
            if response is None:
                return False
        return True
