#!/usr/bin/env bash
# macOS .app paketi — Akilli Sicak Satis Yonetim Sistemi (VanSales)
#
# Calistirma (bir Mac ya da macOS CI uzerinde):
#     chmod +x build_macos.sh && ./build_macos.sh
# Cikti:
#     dist/VanSales.app  ve  dist/VanSales-macOS.zip
#
# Not: desktop/van_sales.spec SPECPATH-goreli ve tasinabilirdir; ancak spec'te
# macOS BUNDLE bolumu olmadigindan .app uretmez. Bu betik ayni girdileri
# (giris betigi, veri dosyalari, gizli ice aktarmalar, haric tutmalar) CLI
# bayraklariyla kurup --windowed ile gercek bir .app paketi olusturur.
#
# UYARI: "set -u" EKLEME — macOS'un bash 3.2'si bos dizi acilimini
# ("${ICON_ARGS[@]}" gibi) unbound variable sayar ve betik duser.
set -eo pipefail

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "HATA: macOS .app paketi bir Mac uzerinde olusturulmalidir."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r backend/requirements.txt
# pywebview macOS'ta pyobjc bagimliliklarini kendisi getirir; paket icinde
# yoksa masaustu.py varsayilan tarayiciya duser.
"$PYTHON_BIN" -m pip install pyinstaller pywebview

# Arayuz derlemesi: frontend/dist git'e girmez (bkz. .gitignore), CI'da her
# seferinde uretilir. Yerelde hazir dist varsa dokunulmaz.
if [[ ! -f frontend/dist/index.html ]]; then
  pushd frontend >/dev/null
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  npm run build
  popd >/dev/null
fi
[[ -f frontend/dist/index.html ]] || { echo "HATA: Arayuz derlenemedi (frontend/dist/index.html yok)."; exit 1; }

rm -rf build/macos dist/VanSales dist/VanSales.app dist/VanSales-macOS.zip
mkdir -p build/macos

# Ikon: projede logo gorseli yok; ileride desktop/van_sales.png eklenirse
# buradan otomatik .icns uretilir. Windows .ico macOS'ta GECERSIZDIR.
ICON_ARGS=()
if command -v sips >/dev/null && command -v iconutil >/dev/null && [[ -f desktop/van_sales.png ]]; then
  ICONSET="build/macos/VanSales.iconset"
  mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" desktop/van_sales.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" desktop/van_sales.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o build/macos/VanSales.icns
  ICON_ARGS=(--icon "$PROJECT_ROOT/build/macos/VanSales.icns")
fi

# --add-data degerlerinde MUTLAK yol kullanilir: --specpath nedeniyle goreli
# yollar spec dizinine gore cozulur ve derleme sessizce yanlis olurdu.
DATA_ARGS=(
  --add-data "$PROJECT_ROOT/frontend/dist:frontend/dist"
  --add-data "$PROJECT_ROOT/backend/app/locales:app/locales"
)
[[ -f .env.example ]] && DATA_ARGS+=(--add-data "$PROJECT_ROOT/.env.example:.")

# `app` paketi (backend/) hem analizde hem --collect-submodules'un yardimci
# sureclerinde ice aktarilabilir olmali.
export PYTHONPATH="$PROJECT_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --onedir --windowed \
  --workpath build/macos/pyinstaller --specpath build/macos \
  --name VanSales \
  --osx-bundle-identifier "com.vansales.desktop" \
  --paths "$PROJECT_ROOT/backend" \
  "${ICON_ARGS[@]}" "${DATA_ARGS[@]}" \
  --collect-submodules app \
  --collect-submodules uvicorn \
  --collect-submodules webview --collect-data webview \
  --hidden-import sqlalchemy.dialects.sqlite \
  --exclude-module pytest --exclude-module _pytest --exclude-module mypy \
  --exclude-module ruff --exclude-module IPython --exclude-module jupyter \
  --exclude-module tkinter --exclude-module matplotlib \
  --exclude-module pip_audit --exclude-module coverage \
  "$PROJECT_ROOT/desktop/masaustu.py"

APP_PATH="dist/VanSales.app"
[[ -d "$APP_PATH" ]] || { echo "HATA: $APP_PATH olusturulamadi."; exit 1; }

ditto -c -k --keepParent "$APP_PATH" "dist/VanSales-macOS.zip"
echo "Tamamlandi: $APP_PATH"
echo "Dagitim ZIP'i: dist/VanSales-macOS.zip"
