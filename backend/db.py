import os
import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"])
    return _pool

# Every statement is safe to run again, so startup applies it each time and
# upgrades an existing database in place.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Added after launch. ADD COLUMN IF NOT EXISTS upgrades the live
-- database in place on the next startup; rows uploaded before
-- this have no stored file and fall back to the text view.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_type TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file BYTEA;

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-page text, so answers can cite pages. NULL for .txt uploads and for
-- documents uploaded before this column existed.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pages TEXT[];
"""

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)

async def close_db():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None