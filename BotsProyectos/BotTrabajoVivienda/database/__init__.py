"""Database module"""
from .db import (
    get_connection,
    init_database,
    get_or_create_user,
    save_search,
    get_user_searches
)

__all__ = [
    'get_connection',
    'init_database',
    'get_or_create_user',
    'save_search',
    'get_user_searches'
]
