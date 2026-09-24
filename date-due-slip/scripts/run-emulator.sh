#!/usr/bin/env bash
# Launch Pixel_8 with host keyboard + on-screen IME.
#
# Host PC keys always emit Latin scancodes (can't type Cyrillic via hw keyboard).
# Soft Gboard is forced so you can switch to Ukrainian and tap Cyrillic.
set -euo pipefail
AVD="${1:-Pixel_8}"
shift || true
INI="$HOME/.android/avd/${AVD}.avd/config.ini"
if [[ -f "$INI" ]]; then
  sed -i 's/^hw.keyboard=.*/hw.keyboard=yes/' "$INI" || true
  if ! grep -q '^hw.keyboard=' "$INI"; then
    echo 'hw.keyboard=yes' >> "$INI"
  fi
fi

emulator -avd "$AVD" -gpu swiftshader_indirect "$@" &
EMU_PID=$!
adb wait-for-device
# Wait until sys boot completed
for _ in $(seq 1 60); do
  boot=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
  [[ "$boot" == "1" ]] && break
  sleep 2
done
# Critical: with hw.keyboard=yes Android hides Gboard unless this is set
adb shell settings put secure show_ime_with_hard_keyboard 1
wait "$EMU_PID"
