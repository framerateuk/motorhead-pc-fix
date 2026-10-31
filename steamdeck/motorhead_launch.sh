#!/bin/bash
# Motorhead (PC, 1998) Steam Deck / Proton launch wrapper.
#
# Keep it beside game/ and cd/ (build.py puts it there). With the folder at /home/deck/Games/Motorhead:
#   Shortcut target: /home/deck/Games/Motorhead/game/motor.exe, Start In: .../game/
#   Steam > Motorhead > Properties > Launch Options:
#     /home/deck/Games/Motorhead/motorhead_launch.sh %command%
#
# Every launch:
#   1. DLL overrides so Wine loads the ogg-winmm wrapper (winmm.dll beside motor.exe)
#      for CD audio, and dgVoodoo2's ddraw/d3dimm for DirectDraw/Direct3D
#      (glide2x.dll has no Wine builtin, it always loads from the game folder).
#   2. First run only: fake CD-ROM drive (M: or next free letter) in the Proton prefix -> ../cd
#      (holds movies\movies.pak) so the disc check passes and the intro plays.
#
# RENDERER (set before the script path in Launch Options, default dgvoodoo):
#   dgvoodoo  ddraw+d3dimm+glide2x all from dgVoodoo2 2.79.3; pick 3Dfx or D3D in-game
#   wined3d   plain Wine ddraw/d3d; glide2x still dgVoodoo
#   d7vk      GE-Proton 11+: D7VK for Direct3D; menu via Wine ddraw
#   Example:  RENDERER=wined3d /home/deck/Games/Motorhead/motorhead_launch.sh %command%

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HERE/launch.log"
RENDERER="${RENDERER:-dgvoodoo}"
log() { echo "[$(date '+%H:%M:%S')] $*" >>"$LOG"; }
: >"$LOG"
log "args: $*"
log "RENDERER=$RENDERER  STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-unset}"

# --- 1. DLL overrides (Proton appends its own after ours) --------------------
OVR="winmm=n,b"
case "$RENDERER" in
  dgvoodoo) OVR="$OVR;ddraw=n,b;d3dimm=n,b" ;;
  wined3d)  OVR="$OVR;ddraw=b;d3dimm=b" ;;
  d7vk)     export PROTON_USE_D7VK=1; OVR="$OVR;d3dimm=b" ;;
  *)        log "unknown RENDERER '$RENDERER', using dgvoodoo"; OVR="$OVR;ddraw=n,b;d3dimm=n,b" ;;
esac
export WINEDLLOVERRIDES="${OVR}${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
log "WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

# --- 2. Fake CD-ROM drive (first run only) ------------------------------------
# %command% on Deck looks like:  .../reaper SteamLaunch AppId=N -- .../steam-launch-wrapper -- <proton> waitforexitandrun <motor.exe>
# Wine auto-assigns D:, E:, ... to removable media (the Deck's SD card is D:), so we use a
# high letter it never touches. The game scans every drive, so the letter doesn't matter.
PROTON=""
for a in "$@"; do case "$a" in */proton) PROTON="$a"; break;; esac; done
PFX="${STEAM_COMPAT_DATA_PATH:-}/pfx"
WSERVER=""
for c in "$(dirname "$PROTON")/files/bin/wineserver" "$(dirname "$PROTON")/dist/bin/wineserver"; do [ -x "$c" ] && WSERVER="$c" && break; done
if [ -n "$PROTON" ] && [ -n "${STEAM_COMPAT_DATA_PATH:-}" ]; then
  CHANGED=0
  if [ ! -d "$PFX/dosdevices" ]; then
    log "prefix not initialised yet; creating it"
    python3 "$PROTON" run cmd /c exit >>"$LOG" 2>&1
  fi
  # pick a letter: reuse one that already points at our cd folder, else the first free one from M: upward
  CDL=""
  for l in m n o p q r s t u v w x y; do
    if [ -L "$PFX/dosdevices/$l:" ] && [ "$(readlink "$PFX/dosdevices/$l:")" = "$HERE/cd" ]; then CDL="$l"; break; fi
  done
  # a dangling link ending in /cd is ours from before the folder was moved or renamed: repair it
  if [ -z "$CDL" ]; then
    for l in m n o p q r s t u v w x y; do
      if [ -L "$PFX/dosdevices/$l:" ] && [ ! -e "$PFX/dosdevices/$l:" ] && [[ "$(readlink "$PFX/dosdevices/$l:")" == */cd ]]; then
        log "repairing stale link $l: -> $(readlink "$PFX/dosdevices/$l:")"
        rm -f "$PFX/dosdevices/$l:"; CDL="$l"; break
      fi
    done
  fi
  if [ -z "$CDL" ]; then
    for l in m n o p q r s t u v w x y; do
      if [ ! -e "$PFX/dosdevices/$l:" ] && [ ! -L "$PFX/dosdevices/$l:" ]; then CDL="$l"; break; fi
    done
  fi
  if [ -n "$CDL" ] && [ -d "$PFX/dosdevices" ]; then
    if [ ! -L "$PFX/dosdevices/$CDL:" ]; then
      ln -s "$HERE/cd" "$PFX/dosdevices/$CDL:" && log "linked dosdevices/$CDL: -> $HERE/cd"; CHANGED=1
    fi
    if [ -f "$PFX/system.reg" ] && ! grep -q "\"$CDL:\"=\"cdrom\"" "$PFX/system.reg"; then
      log "marking $CDL: as CD-ROM in registry"
      python3 "$PROTON" run reg add 'HKLM\Software\Wine\Drives' /v "$CDL:" /d cdrom /f >>"$LOG" 2>&1; CHANGED=1
    fi
  else
    log "WARNING: no free drive letter M:-Y: for the fake CD"
  fi
  # Wine's mount manager only reads dosdevices + the Drives key at prefix boot, so
  # after changing them make sure the current wineserver is gone before the game starts.
  if [ "$CHANGED" = 1 ] && [ -n "$WSERVER" ]; then
    log "restarting wineserver so the new drive is picked up"
    WINEPREFIX="$PFX" "$WSERVER" -k >>"$LOG" 2>&1; sleep 2
    WINEPREFIX="$PFX" "$WSERVER" -w >>"$LOG" 2>&1
  fi
  log "drive letters: $(ls -l "$PFX/dosdevices" 2>/dev/null | grep -E ' [a-z]:+ ->' | awk '{print $(NF-2), $NF}' | tr '\n' ' ')"
  log "registry Drives: $(grep -A4 'Software\\\\Wine\\\\Drives' "$PFX/system.reg" 2>/dev/null | tr '\n' ' ')"
  if [ "${DIAG:-0}" = 1 ] && [ -n "$CDL" ]; then
    log "DIAG: listing $CDL:\\movies from inside Wine:"
    python3 "$PROTON" run cmd /c "dir $CDL:\\movies" >>"$LOG" 2>&1 || true
  fi
else
  log "WARNING: could not find proton in args or STEAM_COMPAT_DATA_PATH unset; skipping fake CD setup"
fi

log "exec: $*"
exec "$@"
