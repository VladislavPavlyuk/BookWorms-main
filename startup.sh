#!/bin/bash
# Azure App Service Linux (Oryx + output.tar.zst):
# 1) розпакувати архів у $ROOT, якщо ще немає bookworms/manage.py
# 2) msodbcsql18 для pyodbc + Azure SQL
# 3) Gunicorn
#
# У порталі Startup Command: bash startup.sh  (у розпакованому /tmp/... файл є в tarball)
#   або: bash bookworms/azure_startup.sh → викликає цей же скрипт з репо (bookworms/azure_startup.sh)
set -e
_HERE="${BASH_SOURCE[0]}"
if [[ "$_HERE" == */* ]]; then
  _START="$(cd "$(dirname "$_HERE")" && pwd)"
else
  _START="$(pwd)"
fi
ROOT=""
_d="$_START"
while [ "$_d" != "/" ]; do
  if [ -f "$_d/bookworms/manage.py" ]; then
    ROOT="$_d"
    break
  fi
  _d="$(dirname "$_d")"
done
if [ -z "$ROOT" ] && [ -f "/home/site/wwwroot/output.tar.zst" ]; then
  ROOT="/home/site/wwwroot"
  cd "$ROOT" || exit 1
  _t="/home/site/wwwroot/output.tar.zst"
  if tar --help 2>&1 | grep -q zstd; then
    tar --zstd -xf "$_t" -C "$ROOT"
  else
    zstd -d "$_t" -o /tmp/oryx-out.tar
    tar -xf /tmp/oryx-out.tar -C "$ROOT"
    rm -f /tmp/oryx-out.tar
  fi
  _d="$ROOT"
  while [ "$_d" != "/" ]; do
    if [ -f "$_d/bookworms/manage.py" ]; then ROOT="$_d"; break; fi
    _d="$(dirname "$_d")"
  done
fi
if [ -z "$ROOT" ] || [ ! -f "$ROOT/bookworms/manage.py" ]; then
  echo "ERROR: cannot find app root (bookworms/manage.py) starting from $_START"
  exit 1
fi
cd "$ROOT" || { echo "ERROR: cd $ROOT failed"; exit 1; }

if [ ! -x "$ROOT/antenv/bin/python" ]; then
  _py="$(find /tmp -maxdepth 6 -type f -path '*/antenv/bin/python' 2>/dev/null | head -n 1)"
  if [ -n "$_py" ]; then
    _nr="$(cd "$(dirname "$_py")/../.." && pwd)"
    if [ -f "$_nr/bookworms/manage.py" ]; then
      ROOT="$_nr"
      cd "$ROOT" || exit 1
    fi
  fi
fi
if [ ! -x "$ROOT/antenv/bin/python" ]; then
  echo "ERROR: antenv not found (ROOT=$ROOT)."
  exit 1
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
