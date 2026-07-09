# QData Dev Log

## 2026-07-09 — Edit connection not persisting config fix

**Bug**: Editing a connection (e.g., changing database name) via the Connections form would update `connection_string` in the DB but NOT `config.db_fields`. On re-open, the form showed old values.

**Root cause**: `update_datasource` in `datasources.py:268-270` modified `ds.config` in-place with the same Python dict object reference. SQLAlchemy's change tracking for `Column(JSON)` compares by identity (`is`), so assigning the same dict back was treated as "not modified" and the column was excluded from the UPDATE query.

**Fix**: Changed to create a brand-new dict via `{**(ds.config or {}), "db_fields": ...}` so SQLAlchemy sees a new object and marks the column as dirty.

**Affected file**: `backend/qdata/web/routes/datasources.py:268-270`
