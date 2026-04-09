#!/bin/bash
# Azure App Service Linux (Oryx + output.tar.zst / прямий wwwroot):
# 1) розпакувати архів, якщо ще немає bookworms/manage.py
# 2) msodbcsql18 для pyodbc + Azure SQL
# 3) Gunicorn
# Startup Command: bash /home/site/wwwroot/startup.sh
set -e
# НЕ використовуй $HOME: у SSH root має HOME=/root → /root/site/wwwroot не існує.
ROOT="/home/site/wwwroot"
cd "$ROOT" || { echo "ERROR: cd $ROOT failed"; exit 1; }

# Після --compress-destination-dir інколи в wwwroot лише output.tar.zst
if [ ! -f "$ROOT/bookworms/manage.py" ] && [ -f "$ROOT/output.tar.zst" ]; then
  if tar --help 2>&1 | grep -q zstd; then
    tar --zstd -xf "$ROOT/output.tar.zst" -C "$ROOT"
  else
    zstd -d "$ROOT/output.tar.zst" -o /tmp/oryx-out.tar
    tar -xf /tmp/oryx-out.tar -C "$ROOT"
    rm -f /tmp/oryx-out.tar
  fi
fi

if command -v odbcinst >/dev/null 2>&1 && odbcinst -q -d 2>/dev/null | grep -qi "ODBC Driver 18"; then
  :
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y curl gnupg ca-certificates
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
  if grep -qi ubuntu /etc/os-release 2>/dev/null; then
    # Noble = 24.04 у логах Oryx; підставляється VERSION_ID з /etc/os-release
    . /etc/os-release
    UBUNTU_VER="${VERSION_ID:-22.04}"
    curl -fsSL "https://packages.microsoft.com/config/ubuntu/${UBUNTU_VER}/prod.list" -o /etc/apt/sources.list.d/microsoft-prod.list
  else
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list
  fi
  apt-get update -y
  ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc
fi

PORT="${WEBSITES_PORT:-8000}"
exec "$ROOT/antenv/bin/gunicorn" --bind="0.0.0.0:${PORT}" --chdir "$ROOT/bookworms" bookworms.wsgi:application
