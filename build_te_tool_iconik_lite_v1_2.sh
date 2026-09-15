#!/usr/bin/env bash
set -euo pipefail

APP_NAME="TE Tool Iconik Lite Version"
VERSION="V1_2"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="${ROOT_DIR}/build/${APP_NAME} ${VERSION}"
ZIP_PATH="${ROOT_DIR}/downloads/TE.Tool.Iconik.Lite.Version.${VERSION}.zip"

if [[ -e "${PACKAGE_DIR}" ]]; then
  echo "Package directory already exists: ${PACKAGE_DIR}" >&2
  exit 1
fi

if [[ -e "${ZIP_PATH}" ]]; then
  echo "ZIP already exists: ${ZIP_PATH}" >&2
  exit 1
fi

mkdir -p "${PACKAGE_DIR}/assets" "${PACKAGE_DIR}/tests" "${ROOT_DIR}/downloads"
cp "${ROOT_DIR}/index.html" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/styles.css" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/app.js" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/te_iconik_lite_core.js" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/te_iconik_scanner.py" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/site.webmanifest" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/release_source.json" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/README.md" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/CHANGELOG.md" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/VERSION" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/requirements.txt" "${PACKAGE_DIR}/"
cp "${ROOT_DIR}/assets/te-tool-iconik-lite.png" "${PACKAGE_DIR}/assets/"
cp "${ROOT_DIR}/tests/test_scanner.py" "${PACKAGE_DIR}/tests/"
cp "${ROOT_DIR}/tests/core.test.js" "${PACKAGE_DIR}/tests/"

(
  cd "${ROOT_DIR}/build"
  zip -qry "${ZIP_PATH}" "${APP_NAME} ${VERSION}"
)

echo "Created ${ZIP_PATH}"
