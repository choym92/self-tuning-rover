#!/usr/bin/env bash
# Write the JetPack 6.2.1 SD image to the NVMe SSD and point the SSD copy's
# boot config at the SSD. Runs ON THE JETSON while booted from the microSD.
# The microSD is never written. Usage:
#   bash jetson-nvme-install.sh --check         # read-only guards only, no root needed
#   sudo bash jetson-nvme-install.sh            # full run, asks for "yes" before writing
#   sudo bash jetson-nvme-install.sh --verify-only  # skip the write: verify the SSD, edit its boot config
#   --yes  skips the "Type yes" prompt (for detached runs: setsid nohup ... > log)
set -euo pipefail

MODE="run"
ASSUME_YES=0
for arg in "$@"; do
  case "${arg}" in
    --check|--verify-only) MODE="${arg}" ;;
    --yes) ASSUME_YES=1 ;;
    *) echo "unknown option: ${arg}" >&2; exit 1 ;;
  esac
done

ZIP="/home/paulcho/jetson-orin-nano-devkit-super-SD-image_JP6.2.1.zip"
ZIP_BYTES=11725610175
ZIP_SHA="3cfaa8346b96aa82529cdb72faf4550cbb43ecee1efc6f1b616d52dfe199916d"
IMG_NAME="sd-blob.img"
IMG_BYTES=24086839296
IMG_SHA="f9a4a32021cee3b45af5fc2015d044eb99dc2adbc0640bb46202dc8865e67894"

DISK="nvme0n1"
DEV="/dev/${DISK}"
EXPECTED_MODEL="T-FORCETM8FFE512G"   # sysfs model "T-FORCE TM8FFE512G" with spaces removed
MIN_BYTES=450000000000
MAX_BYTES=520000000000
MNT="/mnt/nvme-root"

fail() { echo "REFUSED: $*" >&2; exit 1; }

echo "== Guards (read-only) =="

[ -e "${DEV}" ] || fail "${DEV} does not exist"
[ "$(lsblk -dno TYPE "${DEV}")" = "disk" ] || fail "${DEV} is not a disk"

model="$(tr -d ' ' < "/sys/class/block/${DISK}/device/model")"
[ "${model}" = "${EXPECTED_MODEL}" ] || fail "model is '${model}', expected '${EXPECTED_MODEL}'"

size_bytes=$(( $(cat "/sys/class/block/${DISK}/size") * 512 ))
[ "${size_bytes}" -ge "${MIN_BYTES}" ] && [ "${size_bytes}" -le "${MAX_BYTES}" ] \
  || fail "size ${size_bytes} bytes is outside ${MIN_BYTES}..${MAX_BYTES}"

root_src="$(findmnt -no SOURCE /)"
[ "${root_src}" = "/dev/mmcblk0p1" ] || fail "running root is ${root_src}, expected /dev/mmcblk0p1 (microSD)"

if lsblk -no MOUNTPOINT "${DEV}" | grep -q .; then
  fail "something on ${DEV} is mounted"
fi

[ -f "${ZIP}" ] || fail "zip not found: ${ZIP}"
zip_size="$(stat -c %s "${ZIP}")"
[ "${zip_size}" -eq "${ZIP_BYTES}" ] || fail "zip size ${zip_size}, expected ${ZIP_BYTES}"

img_listed="$(unzip -l "${ZIP}" | awk -v n="${IMG_NAME}" '$4 == n { print $1 }')"
[ "${img_listed}" = "${IMG_BYTES}" ] || fail "zip lists ${IMG_NAME} as '${img_listed}' bytes, expected ${IMG_BYTES}"

for t in unzip dd sha256sum partprobe lsblk findmnt sed; do
  command -v "${t}" > /dev/null || fail "missing tool: ${t}"
done

if [ "${MODE}" != "--verify-only" ]; then
  echo "Checking zip SHA-256 (about 2 minutes)..."
  zip_sha="$(sha256sum "${ZIP}" | awk '{ print $1 }')"
  [ "${zip_sha}" = "${ZIP_SHA}" ] || fail "zip SHA-256 mismatch: ${zip_sha}"
fi

echo "Target : ${DEV} (${model}, ${size_bytes} bytes)"
echo "Source : ${ZIP} -> ${IMG_NAME} (${IMG_BYTES} bytes)"
echo "Root   : ${root_src} (microSD, untouched)"
echo "All guards passed."

if [ "${MODE}" = "--check" ]; then
  echo "Check mode: stopping before any write."
  exit 0
fi

[ "$(id -u)" -eq 0 ] || fail "must run as root (sudo) for the real run"

echo
if [ "${MODE}" = "--verify-only" ]; then
  echo "Verify-only: ${DEV} will NOT be rewritten; its boot config will be edited after verification."
else
  echo "This will ERASE ${DEV} and write the JetPack image to it."
fi
if [ "${ASSUME_YES}" -eq 1 ]; then
  echo "--yes given; continuing without prompt."
else
  read -r -p "Type yes to continue: " answer
  [ "${answer}" = "yes" ] || { echo "Aborted; nothing written."; exit 0; }
fi

if [ "${MODE}" != "--verify-only" ]; then
  echo
  echo "== Write =="
  unzip -p "${ZIP}" "${IMG_NAME}" \
    | dd of="${DEV}" bs=4M iflag=fullblock oflag=direct conv=fsync status=progress
  sync
  partprobe "${DEV}" || true
  sleep 2
fi

echo
echo "== Partition table on ${DEV} =="
lsblk -o NAME,SIZE,FSTYPE,PARTLABEL "${DEV}"
part_count="$(lsblk -no NAME "${DEV}" | grep -c "${DISK}p")"
[ "${part_count}" -eq 15 ] || fail "expected 15 partitions, found ${part_count}"
[ "$(lsblk -no PARTLABEL "${DEV}p1")" = "APP" ] || fail "${DEV}p1 is not labeled APP"

if lsblk -no MOUNTPOINT "${DEV}" | grep -q .; then
  lsblk -o NAME,MOUNTPOINT "${DEV}"
  fail "a partition on ${DEV} was auto-mounted after the write; unmount it and re-run (the hash check below would fail)"
fi

echo
echo "== Verify: SHA-256 of the first ${IMG_BYTES} bytes read back from ${DEV} =="
# Exact block count, no `head`: a truncating `head` makes dd die of SIGPIPE,
# which under `set -eo pipefail` kills the script silently.
IMG_MIB=22971
[ $(( IMG_MIB * 1048576 )) -eq "${IMG_BYTES}" ] || fail "IMG_MIB does not match IMG_BYTES"
read_sha="$(dd if="${DEV}" bs=1M count="${IMG_MIB}" iflag=direct,fullblock status=progress \
  | sha256sum | awk '{ print $1 }')"
echo "expected ${IMG_SHA}"
echo "got      ${read_sha}"
[ "${read_sha}" = "${IMG_SHA}" ] || fail "verification FAILED; nothing edited. Re-run the script."
echo "Verification passed."

echo
echo "== Edit boot config on the SSD copy =="
mkdir -p "${MNT}"
mount "${DEV}p1" "${MNT}"
trap 'sync; umount "${MNT}" 2> /dev/null || true' EXIT

ext="${MNT}/boot/extlinux/extlinux.conf"
[ "$(grep -c 'root=/dev/mmcblk0p1' "${ext}")" -eq 1 ] || fail "unexpected extlinux.conf content"
cp -a "${ext}" "${ext}.orig"
sed -i 's|root=/dev/mmcblk0p1|root=/dev/nvme0n1p1|' "${ext}"
[ "$(grep -c 'root=/dev/nvme0n1p1' "${ext}")" -eq 1 ] || fail "extlinux.conf edit failed"
[ "$(grep -c 'mmcblk0' "${ext}")" -eq 0 ] || fail "extlinux.conf still mentions mmcblk0"
echo "extlinux.conf: $(grep -o 'root=[^ ]*' "${ext}")"

# The fresh image has no TEGRA_BOOT_STORAGE line: nv-l4t-bootloader-config.sh
# adds it on first boot from the UEFI BootCurrent device (nvme0n1 here).
bc="${MNT}/etc/nv_boot_control.conf"
if grep -q '^TEGRA_BOOT_STORAGE' "${bc}"; then
  [ "$(grep -c '^TEGRA_BOOT_STORAGE mmcblk0$' "${bc}")" -eq 1 ] || fail "unexpected nv_boot_control.conf content"
  cp -a "${bc}" "${bc}.orig"
  sed -i 's|^TEGRA_BOOT_STORAGE mmcblk0$|TEGRA_BOOT_STORAGE nvme0n1|' "${bc}"
  [ "$(grep -c '^TEGRA_BOOT_STORAGE nvme0n1$' "${bc}")" -eq 1 ] || fail "nv_boot_control.conf edit failed"
  echo "nv_boot_control.conf: $(grep '^TEGRA_BOOT_STORAGE' "${bc}")"
else
  echo "nv_boot_control.conf: no TEGRA_BOOT_STORAGE line (fresh image); first boot will add it"
fi

echo
echo "== fstab on the SSD copy (for the log) =="
cat "${MNT}/etc/fstab"

sync
umount "${MNT}"
trap - EXIT

echo
echo "DONE. Next: sudo shutdown -h now, remove the microSD, power on."
echo "The Jetson should boot from the SSD and show the first-boot setup."
