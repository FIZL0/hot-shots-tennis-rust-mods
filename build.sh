#!/usr/bin/env bash
# Build the mods in out/mods/ from your own discs, with the stats, voices and reactions in tools/rerig/*_data.py.
#
#   ./build.sh            every supported disc found under iso/ (or already unpacked in extracted/<game>/)
#   ./build.sh fore oob   just those games
#
# Drop disc images anywhere under iso/: PS2/PSP .iso files, and Out of Bounds as its decrypted PS3 folder
# (the one with PS3_DISC.SFB). Discs are recognised by their ID, not their filename.
set -euo pipefail
cd "$(dirname "$0")"
JOBS=${JOBS:-$(nproc)}
HST=../HST-Remastered/context/xb

# disc ID -> game (the US releases; the exporters' paths are only known for these)
game_of() {
  case "$1" in
    SCUS_974.01) echo fore ;;
    UCUS-98701) echo getagrip ;;
    UCUS-98614) echo opentee ;;
    UCUS-98693) echo opentee2 ;;
    BCUS-98115) echo oob ;;
  esac
}

disc_id() {  # PSP: UMD_DATA.BIN starts with the ID; PS2: SYSTEM.CNF names the boot ELF
  local id
  id=$(7z e -so "$1" UMD_DATA.BIN 2>/dev/null | head -c 10 || true)
  [ -n "$id" ] && { echo "$id"; return; }
  7z e -so "$1" SYSTEM.CNF 2>/dev/null | grep -ao 'S[A-Z]\{3\}_[0-9]\{3\}\.[0-9]\{2\}' | head -1 || true
}

# find discs: fills SRC[game]=path for each one under iso/
declare -A SRC
find_discs() {
  local f g
  while IFS= read -r -d '' f; do
    g=$(game_of "$(disc_id "$f")")
    [ -n "$g" ] && [ -z "${SRC[$g]:-}" ] && SRC[$g]=$f
  done < <(find -L iso -iname '*.iso' -print0 2>/dev/null)
  while IFS= read -r -d '' f; do
    g=$(game_of "$(grep -ao 'BCUS-[0-9]\{5\}' "$f" | head -1)")
    [ -n "$g" ] && [ -z "${SRC[$g]:-}" ] && SRC[$g]=$(dirname "$f")
  done < <(find -L iso -name PS3_DISC.SFB -print0 2>/dev/null)
}

unpack() {  # disc -> extracted/<game>/ (skipped when already there)
  local g=$1 src=${SRC[$1]:-}
  [ -e "extracted/$g" ] && return
  [ -n "$src" ] || { echo "$g: no disc found under iso/"; exit 1; }
  mkdir -p extracted
  if [ -d "$src" ]; then ln -s "$(realpath "$src")" "extracted/$g"
  else 7z x -y -o"extracted/$g" "$src" >/dev/null; fi
}

export_models() {
  case "$1" in
    fore) tools/fore2gltf/target/release/fore2gltf fore out/files/fore out ;;
    getagrip) python3 tools/psp2gltf/export_getagrip.py && python3 tools/psp2gltf/export_getagrip_faces.py ;;
    opentee) python3 tools/psp2gltf/export_opentee.py ;;
    opentee2) python3 tools/psp2gltf/export_opentee2.py ;;
    oob) python3 tools/oob2gltf/export.py ;;
  esac
}

build() {
  local g=$1
  echo "== $g"
  unpack "$g"
  tools/unxb/target/release/unxb "extracted/$g/" "out/files/$g"
  # Open Tee's face emotions are read off Open Tee 2's face animations (opentee_data.py _tats)
  if [ "$g" = opentee ] && [ ! -d out/files/opentee2 ]; then
    if have opentee2; then unpack opentee2; tools/unxb/target/release/unxb extracted/opentee2/ out/files/opentee2
    else echo "note: no Open Tee 2; Open Tee faces get no emotion textures"; fi
  fi
  # Open Tee 2's pc00-09 winning lines are Open Tee's own hy_NN banks (opentee_data.py voices)
  if [ "$g" = opentee2 ] && [ ! -d out/audio/opentee ]; then
    if have opentee; then
      unpack opentee; tools/unxb/target/release/unxb extracted/opentee/ out/files/opentee
      python3 tools/audio.py opentee "$JOBS"
    else echo "note: no Open Tee; Open Tee 2 pc00-09 get no winning lines (voice programs 7, 9)"; fi
  fi
  export_models "$g"
  python3 tools/audio.py "$g" "$JOBS"
  python3 tools/voices.py
  python3 tools/rerig/batch.py "$g"
  python3 tools/rerig/package.py "$g"
}

for t in cargo python3 7z vgmstream-cli ffmpeg; do
  command -v $t >/dev/null || { echo "missing $t (see README, Requirements)"; exit 1; }
done
# HST's own data, for stat ranks (TParam.csv) and reaction timing (PCANI): required, or mods would silently keep the donor's stats
[ -d "$HST" ] || { echo "missing $HST (HST's extracted disc data; see ../HST-Remastered/research/README.md): needed for the mods' stats and reaction timing"; exit 1; }

have() { [ -n "${SRC[$1]:-}" ] || [ -e "extracted/$1" ]; }

find_discs
if [ $# -gt 0 ]; then WANT=" $* "
else
  WANT=" "
  for g in getagrip fore opentee opentee2 oob; do have "$g" && WANT+="$g "; done
  [ "$WANT" != " " ] || { echo "no supported discs under iso/ (see README)"; exit 1; }
fi
# golf mods borrow Get a Grip's starting racket and Emi's grip (package.py GAG_RACKET, GAG_GRIP)
if [[ "$WANT" =~ fore|opentee|oob ]] && [ ! -d out/rerig/getagrip/pc00_emi ] && [[ "$WANT" != *" getagrip "* ]]; then
  if have getagrip; then WANT+="getagrip "; else echo "note: no Get a Grip; golf mods get no racket.glb"; fi
fi
GAMES=""
for g in getagrip fore opentee opentee2 oob; do [[ "$WANT" == *" $g "* ]] && GAMES+="$g "; done  # Get a Grip first
echo "building: $GAMES"

cargo build -q --release --manifest-path tools/unxb/Cargo.toml
[[ " $GAMES " == *" fore "* ]] && cargo build -q --release --manifest-path tools/fore2gltf/Cargo.toml
for g in $GAMES; do build "$g"; done
echo "done: $(ls out/mods | wc -l) mods in out/mods/"
