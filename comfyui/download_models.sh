#!/usr/bin/env bash
# Download an anime-style Stable Diffusion 1.5 checkpoint for ComfyUI.
#
# Models are NOT committed to this repo (see DISCLAIMER.md). Verify the license
# of whichever checkpoint you use (typically CreativeML OpenRAIL-M).
#
# Usage:
#   ./comfyui/download_models.sh                       # uses defaults below
#   SD_MODEL_URL=https://.../model.safetensors \
#   SD_CHECKPOINT=mymodel.safetensors ./comfyui/download_models.sh
#
# The file is written to ./models/comfyui/checkpoints/<SD_CHECKPOINT>, which is
# mounted into the comfyui service at /models (see docker-compose.yml).
set -euo pipefail

DEST_DIR="${DEST_DIR:-./models/comfyui/checkpoints}"
SD_CHECKPOINT="${SD_CHECKPOINT:-anything-v5.safetensors}"
# Default: Anything V5 (anime SD1.5). Override SD_MODEL_URL for another model.
SD_MODEL_URL="${SD_MODEL_URL:-https://huggingface.co/stablediffusionapi/anything-v5/resolve/main/anything-v5.safetensors}"

mkdir -p "$DEST_DIR"
DEST="$DEST_DIR/$SD_CHECKPOINT"

if [ -f "$DEST" ]; then
  echo "Already present: $DEST"
  exit 0
fi

echo "Downloading checkpoint:"
echo "  from: $SD_MODEL_URL"
echo "  to:   $DEST"
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 -o "$DEST.part" "$SD_MODEL_URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$DEST.part" "$SD_MODEL_URL"
else
  echo "error: need curl or wget" >&2
  exit 1
fi
mv "$DEST.part" "$DEST"
echo "Done. Set SD_CHECKPOINT=$SD_CHECKPOINT in .env if you used a custom name."
