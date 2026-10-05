"""Composition root for library persistence (DIP)."""
from __future__ import annotations

from .ports import ILibraryRepository
from .repository import LibraryRepository

_library_repo: ILibraryRepository = LibraryRepository()


def get_library_repository() -> ILibraryRepository:
    return _library_repo


def set_library_repository(repo: ILibraryRepository) -> None:
    global _library_repo
    _library_repo = repo


def reset_library_defaults() -> None:
    set_library_repository(LibraryRepository())
