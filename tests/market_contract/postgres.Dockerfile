FROM postgres:17-alpine

# Keep the deterministic, disposable market-source contract fixture inside the
# image.  A PostgreSQL container runs its init scripts as uid 70; NAS-backed
# bind mounts can make a host-readable file inaccessible to that uid.
COPY tests/market_contract/init.sql /docker-entrypoint-initdb.d/init.sql
