"""Column types that are Postgres-native in production but still work on SQLite in unit tests."""

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

StringArray = ARRAY(String(64)).with_variant(JSON(), "sqlite")
JsonDict = JSONB().with_variant(JSON(), "sqlite")
