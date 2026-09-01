<#
.SYNOPSIS
    Masaüstü uygulamasını (tek klasör, kurulum gerektirmeyen) paketler.

.DESCRIPTION
    Sırasıyla: paketleme bağımlılıklarını doğrular, arayüzü (gerekirse)
    derler, PyInstaller ile paketler ve sonucu bildirir.
    Çıktı: dist\VanSales\VanSales.exe

.PARAMETER ArayuzuDerle
    frontend\dist hazır olsa bile arayüzü yeniden derler.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\masaustu-paketle.ps1
    powershell -ExecutionPolicy Bypass -File scripts\masaustu-paketle.ps1 -ArayuzuDerle
#>
[CmdletBinding()]
param(
    [switch]$ArayuzuDerle
)

$ErrorActionPreference = 'Stop'
$KOK = Split-Path -Parent $PSScriptRoot
$VENV_PY = Join-Path $KOK '.venv\Scripts\python.exe'

function Baslik($metin) {
    Write-Host ''
    Write-Host "  $metin" -ForegroundColor Cyan
    Write-Host ('  ' + ('-' * $metin.Length)) -ForegroundColor DarkGray
}

if (-not (Test-Path $VENV_PY)) {
    throw "Sanal ortam bulunamadı: $VENV_PY`nÖnce setup.ps1 çalıştırın."
}

# --------------------------------------------------------------- 1. bağımlılık
Baslik '1 · Paketleme bağımlılıkları'

# `pip show`, paket yoksa stderr'e yazar; $ErrorActionPreference='Stop' altında
# bu ölümcül hataya dönüşür. Bunun yerine sessiz bir içe aktarma denemesi
# yapılır: yalnızca çıkış kodu üretir.
function Modul-Var([string]$ad) {
    & $VENV_PY -c "import importlib.util as u, sys; sys.exit(0 if u.find_spec('$ad') else 1)"
    return $LASTEXITCODE -eq 0
}

function Modulu-Sagla([string]$paket, [string]$modul) {
    if (Modul-Var $modul) {
        Write-Host "  [OK] $paket kurulu" -ForegroundColor Green
        return
    }
    Write-Host "  $paket kuruluyor..." -ForegroundColor Yellow
    & $VENV_PY -m pip install $paket --quiet
    if ($LASTEXITCODE -ne 0) { throw "$paket kurulamadı." }
    Write-Host "  [OK] $paket kuruldu" -ForegroundColor Green
}

Modulu-Sagla 'pyinstaller' 'PyInstaller'
Modulu-Sagla 'pywebview' 'webview'

# ----------------------------------------------------------------- 2. arayüz
$indexYolu = Join-Path $KOK 'frontend\dist\index.html'

if ($ArayuzuDerle -or -not (Test-Path $indexYolu)) {
    Baslik '2 · Arayüz derlemesi'
    Push-Location (Join-Path $KOK 'frontend')
    try {
        if (-not (Test-Path 'node_modules')) {
            Write-Host '  Bağımlılıklar kuruluyor...' -ForegroundColor Yellow
            & npm install
            if ($LASTEXITCODE -ne 0) { throw 'npm install başarısız.' }
        }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Arayüz derlemesi başarısız.' }
    }
    finally { Pop-Location }
    Write-Host '  [OK] Derlendi' -ForegroundColor Green
}
else {
    Baslik '2 · Arayüz derlemesi (hazır dist kullanılıyor)'
    Write-Host '  Yeniden derlemek için: -ArayuzuDerle' -ForegroundColor DarkGray
}

if (-not (Test-Path $indexYolu)) {
    throw "Arayüz derlenmemiş: $indexYolu"
}

# ------------------------------------------------------------- 3. paketleme
Baslik '3 · PyInstaller'

Push-Location $KOK
try {
    & $VENV_PY -m PyInstaller --noconfirm 'desktop\van_sales.spec'
    if ($LASTEXITCODE -ne 0) { throw 'Paketleme başarısız.' }
}
finally { Pop-Location }

# ------------------------------------------------------------------ 4. sonuç
Baslik '4 · Sonuç'

$exe = Join-Path $KOK 'dist\VanSales\VanSales.exe'
if (-not (Test-Path $exe)) {
    throw "Beklenen çıktı üretilmedi: $exe"
}

$klasor = Join-Path $KOK 'dist\VanSales'

# Paket denendiğinde uygulama kendi data\, logs\ ve backups\ klasörlerini
# exe'nin yanında oluşturur. Bunlar ÇALIŞMA verisidir; bir sonraki
# paketlemede ya da dağıtım arşivine girerse kullanıcıya başkasının
# veritabanı gider. Temizlenir.
foreach ($artik in @('data', 'logs', 'backups')) {
    $yol = Join-Path $klasor $artik
    if (Test-Path $yol) {
        Remove-Item $yol -Recurse -Force
        Write-Host "  Çalışma verisi temizlendi: $artik\" -ForegroundColor DarkGray
    }
}

$boyut = (Get-ChildItem $klasor -Recurse -File | Measure-Object -Property Length -Sum).Sum

Write-Host ''
Write-Host '  [OK] Paket hazır' -ForegroundColor Green
Write-Host "    Konum   : $klasor"
Write-Host ("    Boyut   : {0:N0} MB" -f ($boyut / 1MB))
Write-Host "    Çalıştır: $exe"
Write-Host ''
Write-Host '  Not: Veritabanı, günlükler ve yedekler exe''nin yanındaki' -ForegroundColor DarkGray
Write-Host '  data\, logs\ ve backups\ klasörlerinde tutulur. Klasörü' -ForegroundColor DarkGray
Write-Host '  taşırken bunları da birlikte taşıyın.' -ForegroundColor DarkGray
Write-Host ''
