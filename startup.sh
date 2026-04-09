#!/bin/bash
# Azure App Service Linux (Oryx + output.tar.zst):
# 1) розпакувати архів у $ROOT, якщо ще немає bookworms/manage.py
# 2) msodbcsql18 для pyodbc + Azure SQL
# 3) Gunicorn
#
# У порталі Startup Command: bash startup.sh  (відносний шлях!)
# Oryx розпаковує output.tar.zst у /tmp/...; у wwwroot немає startup.sh — лише архів.
set -e
# Каталог застосунку: де лежить startup.sh, або cwd (bash startup.sh). Не хардкодь wwwroot — Oryx кладе файли в /tmp/...
_SCRIPT="${BASH_SOURCE[0]}"
if [[ "$_SCRIPT" == */* ]]; then
  ROOT="$(cd "$(dirname "$_SCRIPT")" && pwd)"
else
  ROOT="$(pwd)"
fi
cd "$ROOT" || { echo "ERROR: cd $ROOT failed"; exit 1; }

# Якщо десь ще старий wwwroot, а antenv лише в /tmp після extract — знайти venv
if [ ! -x "$ROOT/antenv/bin/python" ]; then
  _py="$(find /tmp -maxdepth 6 -type f -path '*/antenv/bin/python' 2>/dev/null | head -n 1)"
  if [ -n "$_py" ]; then
    ROOT="$(cd "$(dirname "$_py")/../.." && pwd)"
  fi
fi
if [ ! -x "$ROOT/antenv/bin/python" ]; then
  echo "ERROR: antenv not found (ROOT=$ROOT). Expect Oryx extract under /tmp or cwd."
  exit 1
fi

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
# -m gunicorn: bin/gunicorn часто має shebang на абсолютний шлях з іншого префікса → "required file not found"
exec "$ROOT/antenv/bin/python" -m gunicorn --bind="0.0.0.0:${PORT}" --chdir "$ROOT/bookworms" bookworms.wsgi:application
