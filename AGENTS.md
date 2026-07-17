# QData Dev Log

## 2026-07-09 — pymssql for SQL Server 2014 compatibility

**Problem**: SQL Server 2014 (172.16.0.111, server PRODSEVENDB) gets `08001 10054` (connection reset) or `HYT00` (login timeout) with Microsoft ODBC Driver 17/18 due to TLS version mismatch (ODBC uses OpenSSL, SQL 2014 on Win 2012 R2 doesn't support TLS 1.2 properly).

**Solution**: Switch from `mssql+pyodbc://` (ODBC) to `mssql+pymssql://` (FreeTDS) for all SQL Server connections.

**Changes made**:
- `backend/qdata/web/routes/datasources.py:89-95`: `build_connection_string` now returns `mssql+pymssql://user:pass@host:port/db` (no instance name, no driver query params, no `TrustServerCertificate`)
- `backend/pyproject.toml`: added `"pymssql>=2.3"` to dependencies
- **DB migration**: All 18 existing SQL Server datasources' `connection_string` updated from `mssql+pyodbc://...` to `mssql+pymssql://...` (with instance name removed from URL — pymssql connects by TCP port, not SQL Browser)
- Container not rebuilt yet; `pip install pymssql` runs in current container; rebuild needed after commit.

**Verification**:
- Direct `pymssql.connect(server='172.16.0.111', port=1433, ...)`: ✅ returns SQL Server 2014 SP2 version 12.0.5000.0
- API `POST /datasources/test` with pymssql URL: ✅ returns `{"success":true,"tables":[...7169 tables...]}`
- API `GET /datasources/{id}/tables` for SEVEN: ✅ returns 200 with tables/columns

## Previous work (earlier sessions)

### Drag-and-drop reorder of connections
**Files**: `backend/qdata/web/routes/datasources.py`, frontend components, Alembic migration `c9d8e7f6a5b4`
- Added `sort_order` column to `DataSource` model
- `PUT /datasources/reorder` endpoint for batch reorder
- Frontend: `@dnd-kit` for sortable drag-and-drop with `GripVertical` handle

### ODBC Driver 17 installation
**File**: `Dockerfile` — added `msodbcsql17` alongside `msodbcsql18`
- `_detect_sqlserver_driver()` prefers ODBC 17 before 18
- Was insufficient for SQL Server 2014 (TLS issue persists with both 17 and 18)

### Fix 1 — numpy.int64 serialization crash
**File**: `backend/qdata/web/routes/sources.py:20-37`
**Problem**: `numpy.int64` from `count(*)` caused 500 in `jsonable_encoder`.
**Fix**: `_safe_val` checks `hasattr(v, "item")` before `isinstance(v, (float, int))`.

### Fix 2 — preview always showed 11 total rows
**File**: `backend/qdata/web/routes/sources.py:306-368`
**Fix**: Computes `SELECT COUNT(*)` first, then loads 11 rows for preview.

### Fix 3 — Edit connection not persisting config
**File**: `backend/qdata/web/routes/datasources.py:267-271`
**Fix**: `{**(ds.config or {}), "db_fields": ...}` (new dict) instead of mutating in-place.

### Fix 4 — Various smaller fixes
- **Sources 307 redirect**: Dual decorators `@router.get("")` + `@router.get("/")`
- **SQL Server LIMIT**: `_apply_limit` uses `SELECT TOP n` for SQL Server
- **Preview error display**: `formPreviewError` state with `<AlertTriangle>` in `SourceForm.tsx`
- **Process/report labels**: `_extract_names` regex for `DATABASE=` in ODBC-style Informix/Oracle connections
- **Duplicate UX**: `handleDuplicate` opens form for editing instead of immediate create

## 2026-07-16 — Group permissions & error-action status

### Group-level permissions
**Problem**: Analyst/viewer users could see all analysis groups, processes, and reports — needed scoping to only their own resources plus groups they're explicitly granted access to.

**Changes made**:
- `backend/qdata/db/models.py:154-165`: New `GroupPermission` table (user_id, group_id) with unique constraint
- Alembic migration `e5f6a7b8c9d0` applied
- `backend/qdata/auth/permissions.py:6-14`: `require_role(["admin"])` dependency for protecting delete endpoints
- `backend/qdata/web/routes/groups.py:27-30`: `GET /api/groups` filters by owned + shared groups for non-admin
- `backend/qdata/web/routes/projects.py:37-49`: Dashboard/processes list filters by owned + shared groups
- `backend/qdata/web/routes/reports.py:32-45`: Reports list filters by owned + shared groups
- All DELETE endpoints across `admin.py`, `datasources.py`, `sources.py`, `groups.py`, `projects.py`, `reports.py`, `rules.py`, `scheduler.py` protected with `require_role(["admin"])`
- `backend/qdata/web/routes/admin.py:126-224`: `GET /admin/groups`, `POST /admin/users` (with `group_ids`), `GET/PUT /admin/users/{id}/permissions` for group permission assignment
- `frontend/src/pages/AdminUsers.tsx`: Rewritten with expandable group-permission multi-select and creation-form group assignment
- Delete buttons hidden for non-admin in Groups, Processes, ProcessDetail, Reports, ReportDetail, Connections
- PDF/Excel export endpoints (`reports.py`) also filter by shared groups

### Error-action status tracker
**Problem**: Users needed to track error resolution progress (sin acción / en revisión / solucionado) on rule error detail pages.

**Changes made**:
- `backend/qdata/db/models.py`: Added `ErrorAction` model (report_id, rule_index, error_index, status, updated_at) with unique constraint
- Alembic migration `f0e1d2c3b4a5` applied
- `backend/qdata/web/routes/reports.py`: Added `PUT /reports/{id}/rules/{ri}/errors/{ei}/action` (upsert) and `GET /reports/{id}/rules/{ri}/actions` endpoints
- `frontend/src/pages/ErrorDetail.tsx`: Status dropdown (sin acción → en revisión → solucionado) with arrow navigation; uses `useMutation` for instant updates
- `frontend/src/pages/RuleDetail.tsx`: Green "X solucionados" badge in the rule header card + "Estado" column (dropdown) in the "Detalle de errores" table for per-error status
- TypeScript compiles clean (`npx tsc --noEmit`)
