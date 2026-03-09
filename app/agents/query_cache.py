"""
Query Result Cache

Caches query results to improve performance and reduce LLM calls.
"""

import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, field


logger = logging.getLogger("agents.query_cache")


@dataclass
class CacheEntry:
    """A cached query result"""
    query: str
    sql: str
    result: Dict[str, Any]
    timestamp: datetime
    hit_count: int = 0

    @property
    def age_seconds(self) -> int:
        """Age of cache entry in seconds"""
        return int((datetime.utcnow() - self.timestamp).total_seconds())

    @property
    def size_bytes(self) -> int:
        """Approximate size of cached result in bytes"""
        return len(json.dumps(self.result).encode('utf-8'))


class QueryCache:
    """
    LRU cache for query results.

    Cache entries are evicted based on:
    1. Maximum number of entries
    2. Maximum memory usage
    3. Time-to-live (TTL) expiration
    """

    def __init__(
        self,
        max_entries: int = 1000,
        max_memory_mb: int = 100,
        ttl_seconds: int = 3600  # 1 hour default
    ):
        self.max_entries = max_entries
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_memory_bytes = 0
        self._hits = 0
        self._misses = 0

    def _generate_key(self, query: str, schema_hash: str = "") -> str:
        """Generate cache key from query and schema hash"""
        key_data = f"{query}:{schema_hash}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _compute_schema_hash(self, schema_text: str) -> str:
        """Compute hash of schema text for cache invalidation"""
        return hashlib.md5(schema_text.encode()).hexdigest()[:8]

    def get(self, query: str, schema_text: str = "") -> Optional[Dict[str, Any]]:
        """
        Get cached result for a query.

        Args:
            query: Natural language query
            schema_text: Current database schema (for hash computation)

        Returns:
            Cached result or None if not found/expired
        """
        schema_hash = self._compute_schema_hash(schema_text)
        key = self._generate_key(query, schema_hash)

        if key not in self._cache:
            self._misses += 1
            logger.debug(f"Cache miss: {query[:50]}...")
            return None

        entry = self._cache[key]

        # Check TTL
        if entry.age_seconds > self.ttl_seconds:
            logger.debug(f"Cache entry expired (age={entry.age_seconds}s)")
            del self._cache[key]
            self._current_memory_bytes -= entry.size_bytes
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hit_count += 1
        self._hits += 1

        logger.debug(f"Cache hit: {query[:50]}... (hit count: {entry.hit_count})")

        return entry.result

    def set(
        self,
        query: str,
        sql: str,
        result: Dict[str, Any],
        schema_text: str = ""
    ) -> None:
        """
        Cache a query result.

        Args:
            query: Natural language query
            sql: Generated SQL
            result: Query result to cache
            schema_text: Current database schema
        """
        # Check if result is too large to cache
        result_size = len(json.dumps(result).encode('utf-8'))
        if result_size > self.max_memory_bytes * 0.1:  # Don't cache results > 10% of max
            logger.debug(f"Result too large to cache: {result_size} bytes")
            return

        schema_hash = self._compute_schema_hash(schema_text)
        key = self._generate_key(query, schema_hash)

        # Remove existing entry if present
        if key in self._cache:
            self._current_memory_bytes -= self._cache[key].size_bytes
            del self._cache[key]

        # Evict entries if needed
        self._evict_if_needed(result_size)

        # Add new entry
        entry = CacheEntry(
            query=query,
            sql=sql,
            result=result,
            timestamp=datetime.utcnow()
        )

        self._cache[key] = entry
        self._current_memory_bytes += result_size
        self._cache.move_to_end(key)

        logger.debug(
            f"Cached query: {query[:50]}... "
            f"(size: {result_size} bytes, total entries: {len(self._cache)})"
        )

    def invalidate(self, query: str = None, schema_text: str = "") -> None:
        """
        Invalidate cache entries.

        Args:
            query: Specific query to invalidate (None = invalidate all)
            schema_text: Schema hash to invalidate
        """
        if query is None:
            # Invalidate all
            self._cache.clear()
            self._current_memory_bytes = 0
            logger.info("Cache invalidated: all entries")
        else:
            # Invalidate specific query
            schema_hash = self._compute_schema_hash(schema_text)
            key = self._generate_key(query, schema_hash)
            if key in self._cache:
                self._current_memory_bytes -= self._cache[key].size_bytes
                del self._cache[key]
                logger.info(f"Cache invalidated: {query[:50]}...")

    def _evict_if_needed(self, new_entry_size: int) -> None:
        """Evict entries to make room for new entry"""
        # Check memory limit
        while (self._current_memory_bytes + new_entry_size > self.max_memory_bytes and
               self._cache):
            oldest_key, oldest_entry = self._cache.popitem(last=False)
            self._current_memory_bytes -= oldest_entry.size_bytes
            logger.debug(f"Evicted entry (memory limit): {oldest_entry.query[:50]}...")

        # Check entry limit
        while len(self._cache) >= self.max_entries:
            oldest_key, oldest_entry = self._cache.popitem(last=False)
            self._current_memory_bytes -= oldest_entry.size_bytes
            logger.debug(f"Evicted entry (entry limit): {oldest_entry.query[:50]}...")

        # Evict expired entries
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.age_seconds > self.ttl_seconds
        ]
        for key in expired_keys:
            entry = self._cache.pop(key)
            self._current_memory_bytes -= entry.size_bytes
            logger.debug(f"Evicted expired entry: {entry.query[:50]}...")

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._current_memory_bytes = 0
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "entries": len(self._cache),
            "memory_bytes": self._current_memory_bytes,
            "memory_mb": self._current_memory_bytes / (1024 * 1024),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "max_entries": self.max_entries,
            "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
            "ttl_seconds": self.ttl_seconds
        }

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.age_seconds > self.ttl_seconds
        ]

        for key in expired_keys:
            entry = self._cache.pop(key)
            self._current_memory_bytes -= entry.size_bytes

        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        return len(expired_keys)
