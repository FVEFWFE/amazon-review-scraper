"""
Source adapters for fetching Amazon reviews.
"""

from .base import ReviewSource, SourceType
from .free import FreeSource
from .oxylabs import OxylabsSource

__all__ = ["ReviewSource", "SourceType", "FreeSource", "OxylabsSource"]