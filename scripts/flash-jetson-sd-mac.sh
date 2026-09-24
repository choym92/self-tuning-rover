#!/bin/bash
# Write the JetPack 6.2.1 SD card image to a microSD card, then read the whole
# image length back from the card and compare SHA-256 hashes with the source.
# Guards: abort unless the target is a removable 60-70 GB SD-card-reader disk
# that is not the system disk, and the user types "yes".
set -eu

IMG="$HOME/Downloads/sd-blob.img"
IMG_BYTES=24086839296
DISK="disk4"

echo "== 1. Check image"
[ -f "$IMG" ] || { echo "Image not found: $IMG"; exit 1; }
[ "$(stat -f%z "$IMG")" = "$IMG_BYTES" ] || { echo "Image size does not match. Aborting."; exit 1; }
echo "   $IMG ($IMG_BYTES bytes) OK"

echo "== 2. Check target disk"
INFO=$(diskutil info "/dev/$DISK") || { echo "/dev/$DISK not found. Re-insert the card."; exit 1; }
SIZE=$(echo "$INFO" | awk -F'[()]' '/Disk Size/ {print $2}' | awk '{print $1}')
PROTO=$(echo "$INFO" | awk -F': *' '/Protocol/ {print $2}')
REMOVABLE=$(echo "$INFO" | awk -F': *' '/Removable Media/ {print $2}')
SYSDISK=$(diskutil info / | awk -F': *' '/Part of Whole/ {print $2}')
echo "   /dev/$DISK  size=$SIZE bytes  protocol=$PROTO  removable=$REMOVABLE  (system disk=$SYSDISK)"

[ "$DISK" != "$SYSDISK" ] || { echo "Target is the system disk. Aborting."; exit 1; }
[ "$PROTO" = "Secure Digital" ] || { echo "Target is not an SD card. Aborting."; exit 1; }
[ "$REMOVABLE" = "Removable" ] || { echo "Target is not removable. Aborting."; exit 1; }
if [ "$SIZE" -lt 60000000000 ] || [ "$SIZE" -gt 70000000000 ]; then
  echo "Target is not a 64 GB card. Aborting."; exit 1
fi

echo
read -r -p "This ERASES the SD card above and writes JetPack. Type yes to continue: " ANS
[ "$ANS" = "yes" ] || { echo "Cancelled."; exit 1; }

echo "== 3. Write (10-15 min). Press Ctrl+T to see progress"
diskutil unmountDisk "/dev/$DISK"
sudo dd if="$IMG" of="/dev/r$DISK" bs=4m
sync

echo "== 4. Verify: SHA-256 of the source vs. the same bytes read back from the card (5-10 min)"
SRC_HASH=$(shasum -a 256 "$IMG" | awk '{print $1}')
BLOCKS=$(( (IMG_BYTES + 4194303) / 4194304 ))
CARD_HASH=$(sudo dd if="/dev/r$DISK" bs=4m count="$BLOCKS" 2>/dev/null | head -c "$IMG_BYTES" | shasum -a 256 | awk '{print $1}')
echo "   source: $SRC_HASH"
echo "   card:   $CARD_HASH"
if [ "$SRC_HASH" = "$CARD_HASH" ]; then
  echo "   Verification passed"
else
  echo "   Verification FAILED — the card does not match the source. Re-run or use another card."
  exit 1
fi

echo "== 5. Eject"
diskutil eject "/dev/$DISK"
echo "Done. If macOS says the disk is not readable, click Ignore or Eject (never Initialize)."
echo "Remove the card and insert it into the powered-off Jetson."
