#!/bin/bash
set -e

APP_NAME="セミナーコメント集計ツール"
CERT_NAME="Apple Development: Genki Sasaki (87VY9U4C73)"
DMG_NAME="SeminarCommentSplitter-mac.dmg"

echo "==> Building ${APP_NAME}.app"
uv run pyinstaller \
  --windowed \
  --name "${APP_NAME}" \
  --collect-all customtkinter \
  --collect-all tkinterdnd2 \
  --clean \
  --noconfirm \
  app.py

echo ""
echo "==> Signing with: ${CERT_NAME}"
codesign --force --deep \
  --sign "${CERT_NAME}" \
  --options runtime \
  "dist/${APP_NAME}.app"

codesign --verify --deep --strict "dist/${APP_NAME}.app"
echo "✅ Signed"

echo ""
echo "==> Creating ${DMG_NAME}"
hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "dist/${APP_NAME}.app" \
  -ov -format UDZO \
  "${DMG_NAME}"

echo "✅ ${DMG_NAME} ($(du -sh ${DMG_NAME} | cut -f1))"
