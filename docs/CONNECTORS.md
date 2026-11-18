# Configured connectors

Add the importer account ID to `ANALYST_ADMIN_USER_IDS`. Imports also require write access to the destination project. Connector configuration stays on the backend and the interface lists only the configured names and types. Imports use the same profile, immutable version, and object storage pipeline as uploaded files.

- `ANALYST_POSTGRES_SOURCES` and `ANALYST_MYSQL_SOURCES` map names to read-only connection strings. Set DB credentials with minimal SELECT grants. Imports accept one table or qualified table name. For MySQL, use `mysql+pymysql://` and configure TLS on remote connections.
- `ANALYST_GOOGLE_SHEETS_SOURCES` maps names to an object with `spreadsheet_id` and an A1 `range` including a header row. Use `ANALYST_GOOGLE_SHEETS_API_KEY` for public documents or a read-only OAuth access token in `ANALYST_GOOGLE_SHEETS_ACCESS_TOKEN`. Replace expired OAuth tokens through your secrets manager.
- `ANALYST_REST_SOURCES` maps names to an object with an exact HTTPS `url`, an optional `records_key`, and an optional `bearer` secret. The response must be a JSON array of records at the root or named key. Requests use GET and follow no redirects. To import an API that paginates, configure an endpoint that serves a complete bounded export.

Limits on rows, columns, and stored data size apply to all connectors. Keep credential values in environment secrets and source names free of sensitive information.
