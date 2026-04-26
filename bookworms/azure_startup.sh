#!/usr/bin/env bash
# Тонкий wrapper: у tarball завжди є кореневий startup.sh поруч із bookworms/.
# Портал: bash bookworms/azure_startup.sh  (або простіше - bash startup.sh)
set -e
_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$_ROOT/startup.sh"
