#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_TEXT="$(tr -d '\n' < "${ROOT_DIR}/VERSION")"
VERSION_UNDERSCORE="${VERSION_TEXT//./_}"
APP_NAME="TE Tool Iconik Lite Version ${VERSION_UNDERSCORE}"
BUNDLE_ID="com.michaelbrandonfalk.tetooliconiklite"
ZIP_NAME="TE.Tool.Iconik.Lite.Version.${VERSION_UNDERSCORE}.macOS.Apple.Silicon.zip"
APP_PATH="${ROOT_DIR}/dist/${APP_NAME}.app"
ZIP_PATH="${ROOT_DIR}/downloads/${ZIP_NAME}"
BUILD_DIR="${ROOT_DIR}/build/pyinstaller-${VERSION_UNDERSCORE}"
SPEC_DIR="${ROOT_DIR}/build/spec-${VERSION_UNDERSCORE}"
VENV_DIR="${ROOT_DIR}/.venv-build-${VERSION_UNDERSCORE}"
PYTHON_BIN="${PYTHON_BIN:-${HOME}/.pyenv/versions/3.13.1/bin/python3}"
ICON_PNG="${ROOT_DIR}/assets/te-tool-iconik-lite.png"
ICONSET_DIR="${ROOT_DIR}/build/te-tool-iconik-lite.iconset"
ICON_ICNS="${ROOT_DIR}/build/te-tool-iconik-lite.icns"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo "Using Python: ${PYTHON_BIN}"
echo "Cleaning V1.5 build paths..."
rm -rf "${APP_PATH}" "${BUILD_DIR}" "${SPEC_DIR}" "${VENV_DIR}" "${ZIP_PATH}"
mkdir -p "${ROOT_DIR}/dist" "${ROOT_DIR}/downloads" "${ROOT_DIR}/build"

echo "Creating build virtualenv..."
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt" pyinstaller

ICON_ARGS=()
if [[ -f "${ICON_PNG}" ]] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  rm -rf "${ICONSET_DIR}" "${ICON_ICNS}"
  mkdir -p "${ICONSET_DIR}"
  sips -z 16 16 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_16x16.png" >/dev/null
  sips -z 32 32 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_32x32.png" >/dev/null
  sips -z 64 64 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_128x128.png" >/dev/null
  sips -z 256 256 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_256x256.png" >/dev/null
  sips -z 512 512 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_512x512@2x.png" >/dev/null
  iconutil -c icns "${ICONSET_DIR}" -o "${ICON_ICNS}"
  ICON_ARGS=(--icon "${ICON_ICNS}")
fi

echo "Building ${APP_NAME}.app..."
"${VENV_DIR}/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --windowed \
  --target-architecture arm64 \
  --name "${APP_NAME}" \
  --osx-bundle-identifier "${BUNDLE_ID}" \
  --distpath "${ROOT_DIR}/dist" \
  --workpath "${BUILD_DIR}" \
  --specpath "${SPEC_DIR}" \
  --hidden-import tkinter \
  --collect-all boto3 \
  --collect-all botocore \
  --collect-all s3transfer \
  --collect-all jmespath \
  "${ICON_ARGS[@]}" \
  "${ROOT_DIR}/te_iconik_lite_app.py"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Build failed: ${APP_PATH} was not created." >&2
  exit 1
fi

INFO_PLIST="${APP_PATH}/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "${VERSION_TEXT#V}" "${INFO_PLIST}"
plutil -replace CFBundleVersion -string "${VERSION_TEXT#V}" "${INFO_PLIST}"
plutil -replace CFBundleDisplayName -string "TE Tool Iconik Lite" "${INFO_PLIST}"

echo "Signing app..."
codesign --force --deep --sign - "${APP_PATH}"
codesign --verify --deep --strict --verbose=2 "${APP_PATH}"

echo "Running packaged smoke checks..."
TE_ICONIK_LITE_VERIFY_IMPORTS=1 "${APP_PATH}/Contents/MacOS/${APP_NAME}"
TE_ICONIK_LITE_VERIFY_TK=1 "${APP_PATH}/Contents/MacOS/${APP_NAME}"

echo "Packaging zip..."
find "${APP_PATH}" -name '._*' -type f -delete
COPYFILE_DISABLE=1 ditto -c -k --norsrc --noextattr --keepParent "${APP_PATH}" "${ZIP_PATH}"

echo "Build complete: ${APP_PATH}"
echo "Package complete: ${ZIP_PATH}"
