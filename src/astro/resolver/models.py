"""Pydantic models and enums for the canonical ID resolver."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HashGroupValue = list[str] | Literal["*all"]
HashGroupsConfig = dict[str, HashGroupValue]

_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class EntryStatus(StrEnum):
    NEW = "NEW"
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"


class ResolverConfig(BaseModel):
    """Validated resolver configuration."""

    name: str = Field(min_length=1)
    hash_groups: HashGroupsConfig = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not _SAFE_NAME_PATTERN.match(value):
            raise ValueError("Resolver name must be alphanumeric and may contain '.', '_', or '-'.")
        return value

    @field_validator("hash_groups")
    @classmethod
    def validate_hash_groups(cls, value: HashGroupsConfig) -> HashGroupsConfig:
        for group_name, fields in value.items():
            if not group_name:
                raise ValueError("Hash group names must not be empty.")
            if fields == "*all":
                continue
            if not fields:
                raise ValueError(f"Hash group {group_name!r} must list fields or use '*all'.")
        return value


def hash_column_name(group_name: str) -> str:
    return f"{group_name}_hash"


def changed_column_name(group_name: str) -> str:
    return f"{group_name}_changed"


def namespaced_source_key(namespace: str, raw_key: str) -> str:
    return f"{namespace}:{raw_key}"
