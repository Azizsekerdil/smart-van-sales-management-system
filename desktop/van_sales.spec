# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller yapilandirmasi — Akilli Sicak Satis Yonetim Sistemi masaustu paketi.

Calistirma:
    powershell -ExecutionPolicy Bypass -File scripts\\masaustu-paketle.ps1

Cikti:
    dist\\VanSales\\VanSales.exe   (Windows)
    dist/VanSales/VanSales        (macOS/Linux)

Notlar:
- Tum yollar SPECPATH'e goredir; makineye ozel mutlak yol YOKTUR. Ayni spec
  macOS CI'da da calisir (Windows'a ozgu kisimlar sys.platform ile dallanir).
- `--onedir` (tek klasor) kullanilir, `--onefile` degil. Tek dosya paketi her
  acilista yuzlerce MB'i gecici dizine acar (numpy/pandas ile acilis ciddi
  uzar) ve antivirus yazilimlari bu davranisi sik sik karantinaya alir.
- Yazilabilir veri (veritabani, gunluk, yedek) exe'nin YANINDA tutulur;
  bkz. backend/app/core/config.py IS_FROZEN dallanmasi. Bu olmadan SQLite
  veritabani sys._MEIPASS'a yazilir ve her kapanista silinirdi.
"""

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

KOK = Path(SPECPATH).parent  # noqa: F821 — SPECPATH, PyInstaller tarafindan saglanir
BACKEND = KOK / "backend"
ARAYUZ = KOK / "frontend" / "dist"

# Spec calisma aninda `app` paketi collect_submodules icin ice aktarilabilir
# olmali. PYTHONPATH'e guvenmek yerine burada acikca eklenir.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

if not (ARAYUZ / "index.html").is_file():
    raise SystemExit("Arayuz derlenmemis. Once calistirin:  cd frontend; npm run build")

# Surum, ayarlarin tek dogruluk kaynagindan okunur (Settings.app_version).
_ayar_metni = (BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8")
SURUM = re.search(r'app_version:\s*str\s*=\s*"([^"]+)"', _ayar_metni).group(1)
SURUM_DORTLU = tuple(int(p) for p in (SURUM.split(".") + ["0", "0", "0"])[:4])

# ------------------------------------------------------------------ veriler
# Derlenmis arayuz, gelistirmedeki goreli yerlesimiyle ayni yola gomulur;
# config.FRONTEND_DIST calisma aninda `sys._MEIPASS/frontend/dist` okur.
veriler = [
    (str(ARAYUZ), "frontend/dist"),
    # Ceviri kataloglari (JSON) Python modulu degildir; acikca eklenir.
    (str(BACKEND / "app" / "locales"), "app/locales"),
]

# Ayar sablonu: ilk calistirmada exe'nin yanina kopyalanir (masaustu.py) ve
# yedekleme servisi tarafindan arsive eklenir.
if (KOK / ".env.example").is_file():
    veriler.append((str(KOK / ".env.example"), "."))

# ------------------------------------------------------- gizli ice aktarmalar
# Dinamik yuklenen moduller statik analizde gorunmez.
gizli = [
    *collect_submodules("app"),
    *collect_submodules("uvicorn"),
    "sqlalchemy.dialects.sqlite",
]

# PyWebView istege baglidir: paket icinde varsa pencere acilir, yoksa
# masaustu.py varsayilan tarayiciya duser.
try:
    import webview  # noqa: F401

    veriler += collect_data_files("webview")
    gizli += collect_submodules("webview")
except ImportError:
    pass

# ------------------------------------------------------------- surum kaynagi
# Windows'un dosya ozelliklerinde gorunen bilgi. Kaynak yoksa dosya
# "bilinmeyen yayinci, surumsuz" gorunur. Yalnizca Windows'ta uretilir.
_surum_dosyasi = None
if sys.platform == "win32":
    _surum_icerik = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={SURUM_DORTLU}, prodvers={SURUM_DORTLU},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('041F04B0', [
        StringStruct('CompanyName', 'Van Sales'),
        StringStruct('FileDescription', 'Akıllı Sıcak Satış Yönetim Sistemi'),
        StringStruct('FileVersion', '{SURUM}'),
        StringStruct('InternalName', 'VanSales'),
        StringStruct('LegalCopyright', 'Tüm hakları saklıdır.'),
        StringStruct('OriginalFilename', 'VanSales.exe'),
        StringStruct('ProductName', 'Akıllı Sıcak Satış Yönetim Sistemi'),
        StringStruct('ProductVersion', '{SURUM}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""
    _surum_yolu = KOK / "build" / "surum_bilgisi.txt"
    _surum_yolu.parent.mkdir(parents=True, exist_ok=True)
    _surum_yolu.write_text(_surum_icerik, encoding="utf-8")
    _surum_dosyasi = str(_surum_yolu)

# Ikon: projede logo gorseli bulunmadigindan ikon eklenmez. Eklemek icin
# desktop/van_sales.ico olusturup asagidaki `icon` degerini gecirin.
_ikon = KOK / "desktop" / "van_sales.ico"
_ikon_yolu = str(_ikon) if (sys.platform == "win32" and _ikon.is_file()) else None

a = Analysis(
    [str(KOK / "desktop" / "masaustu.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=veriler,
    hiddenimports=gizli,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Gelistirme araclari pakete girmemeli: boyutu buyuturler ve son
    # kullanicida hicbir islevleri yoktur.
    excludes=[
        "pytest",
        "_pytest",
        "mypy",
        "ruff",
        "IPython",
        "jupyter",
        "tkinter",
        "matplotlib",
        "pip_audit",
        "coverage",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VanSales",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX bazi virus tarayicilarinda yanlis alarm uretir
    console=False,  # pencereli uygulama; hatalar mesaj kutusuyla gosterilir
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ikon_yolu,
    version=_surum_dosyasi,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VanSales",
)
