#!/bin/bash
set -e

APP_NAME="セミナーコメント集計ツール"
CERT_NAME="Developer ID Application: Genki Sasaki (ML6Y87RH9L)"
DMG_NAME="SeminarCommentSplitter-mac.dmg"
NOTARY_PROFILE="semminer-notary"

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

echo ""
echo "==> Notarizing ${DMG_NAME} (数分かかります...)"
xcrun notarytool submit "${DMG_NAME}" \
  --keychain-profile "${NOTARY_PROFILE}" \
  --wait
echo "✅ Notarized"

echo ""
echo "==> Stapling ticket to ${DMG_NAME}"
xcrun stapler staple "${DMG_NAME}"
echo "✅ Stapled"

echo ""
echo "✅ ${DMG_NAME} ($(du -sh ${DMG_NAME} | cut -f1)) — Gatekeeper 通過済み"
