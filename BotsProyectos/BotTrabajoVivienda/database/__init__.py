"""Database module"""
from .db import (
    get_connection,
    init_database,
    get_or_create_user,
    save_search,
    get_user_searches,
    get_all_searches,
    save_jobs,
    save_housing,
    search_jobs_db,
    search_housing_db
)

__all__ = [
    'get_connection',
    'init_database',
    'get_or_create_user',
    'save_search',
    'get_user_searches',
    'get_all_searches',
    'save_jobs',
    'save_housing',
    'search_jobs_db',
    'search_housing_db'
]
