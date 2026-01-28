"""Custom tag category resource wrapper."""

from __future__ import annotations

from typing import Optional, Sequence, cast

from .base import Resource
from ._common_types import ValidationMode, _normalize_color, _normalize_id_sequence, _normalize_id_sequence
from .tag_categories_types import TagCategoryResponse


class TagCategories(Resource):
    """Custom tag category operations."""

    def list(
        self,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TagCategoryResponse] | None:
        """Fetch all tag categories.

        Parameters
        ----------
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        list[TagCategoryResponse] or None
            List of tag category dicts, or ``None`` on error.
        """
        response = self._get("/tags", timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        categories = data.get("categories") if isinstance(data, dict) else None
        if isinstance(categories, list):
            return categories
        self._logger.warning("Tags response missing expected categories list.")
        return None

    def add(
        self,
        label: str,
        *,
        color: Optional[str] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TagCategoryResponse | None:
        """Create a tag category.

        Parameters
        ----------
        label
            Category label.
        color
            Optional category color.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        TagCategoryResponse or None
            Created category dict, or ``None`` on error.
        """
        if not isinstance(label, str) or not label.strip():
            if validation == "strict":
                raise ValueError(f"Invalid label: {label}")
            if validation == "warn":
                self._logger.warning("Invalid label for add: %s", label)
            return None
        
        if color is not None:
            try:
                normalized_color = _normalize_color(color)
            except ValueError as e:
                if validation == "strict":
                    raise ValueError(f"Invalid color: {e}") from e
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid color for add: %s", color)
                    return None
            color = normalized_color

        payload: dict[str, object] = {"label": label}
        if color is not None:
            payload["color"] = color

        response = self._post("/tag-category", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        # The OpenAPI spec says the created category is in `data`, but the API directly returns category objects.
        # Handle both cases until the spec or API is fixed.
        if isinstance(data, dict):
            # This is how the OpenAPI spec says it should be.
            return cast(TagCategoryResponse, data)
        if isinstance(response, dict) and "id" in response:
            # This is how the API actually behaves.
            return cast(TagCategoryResponse, response)
        self._logger.warning("Create tag category response missing expected data. Response was %s", response)
        return None

    def update(
        self,
        category_id: int,
        *,
        label: Optional[str] = None,
        color: Optional[str] = None,
        tags: Optional[Sequence[int]] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TagCategoryResponse | None:
        """Update a tag category.

        Parameters
        ----------
        category_id
            Category identifier.
        label
            New category label.
        color
            New category color.
        tags
            Optional list of tag IDs to assign.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        TagCategoryResponse or None
            Updated category dict, or ``None`` on error.
        """
        if not isinstance(category_id, int) or category_id < 1:
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
        
        if color is not None:
            try:
                normalized_color = _normalize_color(color)
            except ValueError as e:
                if validation == "strict":
                    raise ValueError(f"Invalid color: {e}") from e
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid color for update: %s", color)
                    return None
            color = normalized_color

        payload: dict[str, object] = {"id": category_id}
        if label is not None:
            payload["label"] = label
        if color is not None:
            payload["color"] = color
        if tags is not None:
            normalized_tags = _normalize_id_sequence(tags)
            if normalized_tags is None:
                if validation == "strict":
                    raise ValueError(f"Invalid tags: {tags}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid tags for update: %s", tags)
                    return None
            payload["tags"] = normalized_tags

        if len(payload) == 1:
            self._logger.warning("No updates provided for tag category %s", category_id)
            return None

        response = self._patch("/tag-category", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        # The OpenAPI spec says the updated category is in `data`, but the API directly returns category objects.
        # Handle both cases until the spec or API is fixed.
        if isinstance(data, dict):
            # This is how the OpenAPI spec says it should be.
            return cast(TagCategoryResponse, data)
        if isinstance(response, dict) and "id" in response:
            # This is how the API actually behaves.
            return cast(TagCategoryResponse, response)
        self._logger.warning("Update tag category response missing expected data.")
        return None

    def delete(
        self,
        category_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Delete one or more tag categories by ID.

        Parameters
        ----------
        category_ids
            Category ID or iterable of category identifiers.
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
            ids = [category_ids] if isinstance(category_ids, int) else category_ids
        else:
            # Normalize input to list of IDs with validation
            ids = _normalize_id_sequence(category_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid category_ids: {category_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid category_ids for delete: %s", category_ids)
                    return False

        for category_id in ids:
            response = self._delete("/tag-category", json={"id": category_id}, timeout=timeout)
            if response is None:
                return False
        return True
