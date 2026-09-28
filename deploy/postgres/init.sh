#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=app_password="$STUDIO_APP_PASSWORD" <<'SQL'
CREATE ROLE studio_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB
  NOCREATEROLE NOINHERIT;
CREATE SCHEMA studio AUTHORIZATION CURRENT_USER;
CREATE TABLE studio.sessions (
  session_id text PRIMARY KEY,
  tenant_id text NOT NULL,
  outcome text NOT NULL CHECK (
    outcome IN ('open', 'supported', 'conflicted', 'closed')
  ),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE studio.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio.sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_sessions ON studio.sessions
  FOR ALL TO studio_app
  USING (tenant_id = current_setting('app.tenant_id', true))
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
GRANT USAGE ON SCHEMA studio TO studio_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON studio.sessions TO studio_app;
SQL
