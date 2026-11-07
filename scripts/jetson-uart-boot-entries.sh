#!/usr/bin/env bash
# Add two test boot entries for the /dev/ttyTHS1 DMA bug. Runs ON THE JETSON.
# DEFAULT stays "primary": an entry is used only when picked in the boot menu
# (key 1 = PIO, key 2 = iommus), so a bad entry costs one power cycle.
# Usage:
#   bash jetson-uart-boot-entries.sh --check   # read-only guards and proposed diff, no root
#   sudo bash jetson-uart-boot-entries.sh      # asks for "yes", then writes /boot
set -euo pipefail

MODE="${1:-run}"
case "${MODE}" in --check|run) ;; *) echo "unknown option: ${MODE}" >&2; exit 1 ;; esac

HERE="$(cd "$(dirname "$0")" && pwd)"
EXTLINUX=/boot/extlinux/extlinux.conf
EXTLINUX_SHA=c4480855b4ad0f907a85f4331dde0d6448af8fbe11bcfffc1d05db7249be1cd5
DTB=/boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super.dtb
DTB_SHA=60d07abb4642e14006faae30125737939b463e17bbae2d4129239778cc37866f

fail() { echo "REFUSED: $*" >&2; exit 1; }

echo "== Guards (read-only) =="
[ "$(hostname)" = "paul-cho-jetson" ] || fail "not paul-cho-jetson"
grep -q "R36 (release), REVISION: 5.2" /etc/nv_tegra_release || fail "not L4T R36.5.2"
[ "$(findmnt -no SOURCE /)" = "/dev/nvme0n1p1" ] || fail "root is not /dev/nvme0n1p1"
[ "$(sha256sum "${EXTLINUX}" | cut -d' ' -f1)" = "${EXTLINUX_SHA}" ] || fail "extlinux.conf changed since review"
[ "$(sha256sum "${DTB}" | cut -d' ' -f1)" = "${DTB_SHA}" ] || fail "DTB changed since review"
[ "$(grep -c '^LABEL ' "${EXTLINUX}")" = "1" ] || fail "expected only LABEL primary"
grep -qx "DEFAULT primary" "${EXTLINUX}" || fail "DEFAULT is not primary"
for f in uart1-pio uart1-iommus; do [ -f "${HERE}/${f}.dts" ] || fail "${f}.dts is missing"; done
echo "guards passed"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

echo "== Build and test overlays in ${WORK} =="
for f in uart1-pio uart1-iommus; do dtc -q -@ -I dts -O dtb -o "${WORK}/${f}.dtbo" "${HERE}/${f}.dts"; done
[ "$(fdtget -t s "${WORK}/uart1-pio.dtbo" /fragment@0 delete_prop | tr -d ' ')" != "" ] || fail "delete_prop missing from the PIO overlay"
fdtoverlay -i "${DTB}" -o "${WORK}/iommus-test.dtb" "${WORK}/uart1-iommus.dtbo"
[ "$(fdtget -t x "${WORK}/iommus-test.dtb" /bus@0/serial@3100000 iommus)" = "4 4" ] || fail "iommus overlay gave an unexpected value"
echo "overlays OK"

APPEND_LINE="$(grep -m1 '^ *APPEND ' "${EXTLINUX}")"
{
  sed 's/^TIMEOUT 30$/TIMEOUT 100/' "${EXTLINUX}"
  for entry in "uart-pio|UART test: PIO, DMA off|uart1-pio" "uart-iommus|UART test: DMA with iommus|uart1-iommus"; do
    IFS='|' read -r label title file <<< "${entry}"
    printf 'LABEL %s\n      MENU LABEL %s\n      LINUX /boot/Image\n      FDT %s\n      INITRD /boot/initrd\n%s\n      OVERLAYS /boot/%s.dtbo\n\n' \
      "${label}" "${title}" "${DTB}" "${APPEND_LINE}" "${file}"
  done
} > "${WORK}/extlinux.conf"

echo "== Proposed change to ${EXTLINUX} =="
diff -u "${EXTLINUX}" "${WORK}/extlinux.conf" || true

if [ "${MODE}" = "--check" ]; then
  echo "== --check: nothing was written =="
  exit 0
fi

[ "$(id -u)" = "0" ] || fail "run with sudo to write /boot"
read -r -p "Type yes to write /boot: " answer
[ "${answer}" = "yes" ] || fail "not confirmed"

BACKUP="${EXTLINUX}.before-uart-$(date +%Y%m%d-%H%M%S)"
cp -p "${EXTLINUX}" "${BACKUP}"
install -m 0644 "${WORK}/uart1-pio.dtbo" "${WORK}/uart1-iommus.dtbo" /boot/
install -m 0644 "${WORK}/extlinux.conf" "${EXTLINUX}.new"
mv "${EXTLINUX}.new" "${EXTLINUX}"
sync
cmp "${WORK}/extlinux.conf" "${EXTLINUX}" || fail "written file differs"
grep -qx "DEFAULT primary" "${EXTLINUX}" || fail "DEFAULT changed"
echo "Done. Backup: ${BACKUP}"
echo "Undo: sudo cp -p ${BACKUP} ${EXTLINUX}"
