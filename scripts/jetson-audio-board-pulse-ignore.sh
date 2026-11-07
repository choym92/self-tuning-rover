#!/usr/bin/env bash
# Keep the desktop's PulseAudio (the gdm login-screen session) off the rover audio board, so that
# aplay/arecord on plughw:1,0 never see "Device or resource busy". Runs ON THE JETSON.
# Mechanism: a udev rule sets PULSE_IGNORE=1 on the board's sound card; PulseAudio's
# module-udev-detect skips cards marked so (docs/preflight.md, 2026-11-07).
# Usage:
#   bash jetson-audio-board-pulse-ignore.sh --check   # read-only guards and the proposed rule, no root
#   sudo bash jetson-audio-board-pulse-ignore.sh      # asks for "yes", writes the rule, restarts gdm's PulseAudio
#   sudo bash jetson-audio-board-pulse-ignore.sh --undo
set -euo pipefail

MODE="${1:-run}"
case "${MODE}" in --check|--undo|run) ;; *) echo "unknown option: ${MODE}" >&2; exit 1 ;; esac

VID=0c76; PID=1229                      # JMTek "USB PnP Audio Device" (SSS1629) on the kit's audio board
RULE=/etc/udev/rules.d/89-rover-audio-board-pulse-ignore.rules
RULE_TEXT="# Rover audio board (JMTek ${VID}:${PID}): used directly through ALSA by the rover scripts.
# Keep PulseAudio (gdm login screen, any desktop login) off it. docs/preflight.md 2026-11-07.
SUBSYSTEM==\"sound\", KERNEL==\"card*\", ATTRS{idVendor}==\"${VID}\", ATTRS{idProduct}==\"${PID}\", ENV{PULSE_IGNORE}=\"1\""

fail() { echo "REFUSED: $*" >&2; exit 1; }

echo "== Guards (read-only) =="
[ "$(hostname)" = "paul-cho-jetson" ] || fail "not paul-cho-jetson"
grep -q "R36 (release), REVISION: 5.2" /etc/nv_tegra_release || fail "not L4T R36.5.2"
CARDS=()
for c in /sys/class/sound/card*; do
  [ -r "${c}/device/../idVendor" ] || continue
  if [ "$(cat "${c}/device/../idVendor")" = "${VID}" ] && [ "$(cat "${c}/device/../idProduct")" = "${PID}" ]; then CARDS+=("${c}"); fi
done
[ "${#CARDS[@]}" = "1" ] || fail "expected exactly one ${VID}:${PID} sound card, found ${#CARDS[@]}"
CARD="${CARDS[0]}"
echo "audio board is $(basename "${CARD}") ($(cat "${CARD}/id"))"
GDM_UID="$(id -u gdm 2>/dev/null || true)"
[ -n "${GDM_UID}" ] || fail "no gdm user"
echo "guards passed"

as_gdm_pactl() {  # prints PulseAudio's card list as seen by the gdm session; empty when not reachable
  [ "$(id -u)" = "0" ] || { echo "(needs root to ask gdm's PulseAudio)"; return 0; }
  runuser -u gdm -- env XDG_RUNTIME_DIR="/run/user/${GDM_UID}" pactl list cards short 2>/dev/null || echo "(PulseAudio not reachable)"
}
show_state() {
  echo "-- udev properties of $(basename "${CARD}"):"
  udevadm info -q property -p "${CARD}" | grep -E "^(PULSE_IGNORE|ID_VENDOR_ID|ID_MODEL_ID)=" || true
  echo "-- rule file:"; [ -f "${RULE}" ] && cat "${RULE}" || echo "(absent)"
  echo "-- pulseaudio processes:"; ps -eo user,pid,cmd | grep "[p]ulseaudio" || echo "(none)"
  echo "-- cards known to gdm's PulseAudio:"; as_gdm_pactl
}

echo "== State before =="; show_state
echo "== Proposed rule (${RULE}) =="; echo "${RULE_TEXT}"

if [ "${MODE}" = "--check" ]; then echo "== --check: nothing was written =="; exit 0; fi
[ "$(id -u)" = "0" ] || fail "run with sudo"

if [ "${MODE}" = "--undo" ]; then
  [ -f "${RULE}" ] || fail "nothing to undo, ${RULE} is absent"
  read -r -p "Remove the rule and restart gdm's PulseAudio? type yes: " ANSWER
  [ "${ANSWER}" = "yes" ] || { echo "aborted"; exit 1; }
  rm -f "${RULE}"
else
  [ ! -f "${RULE}" ] || fail "${RULE} already exists (use --undo first)"
  read -r -p "Write the rule and restart gdm's PulseAudio? type yes: " ANSWER
  [ "${ANSWER}" = "yes" ] || { echo "aborted"; exit 1; }
  printf '%s\n' "${RULE_TEXT}" > "${RULE}"; chmod 644 "${RULE}"
fi

udevadm control --reload-rules
udevadm trigger --action=change "${CARD}"
sleep 1
if [ "${MODE}" = "--undo" ]; then
  udevadm info -q property -p "${CARD}" | grep -q "^PULSE_IGNORE=" && fail "PULSE_IGNORE still set after undo" || true
else
  udevadm info -q property -p "${CARD}" | grep -q "^PULSE_IGNORE=1" || fail "PULSE_IGNORE not set after trigger; the rule did not match"
fi

# module-udev-detect reads the property only when it (re)processes the card, so restart the session's
# PulseAudio; the login screen merely loses sound for a second.
if systemctl --machine=gdm@.host --user is-active --quiet pulseaudio.service 2>/dev/null; then
  systemctl --machine=gdm@.host --user restart pulseaudio.service
  sleep 3
else
  echo "gdm's pulseaudio.service is not active; nothing restarted (a reboot applies the rule at next login screen)"
fi

echo "== State after =="; show_state
if [ "${MODE}" = "run" ] && as_gdm_pactl | grep -qi "Solid_State_System\|${VID}"; then
  fail "gdm's PulseAudio still lists the audio board"
fi
echo "done (${MODE})"
