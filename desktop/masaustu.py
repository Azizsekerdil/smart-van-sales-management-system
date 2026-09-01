"""Akilli Sicak Satis Yonetim Sistemi — masaustu baslatici.

Uygulamayi tek bir surec olarak calistirir:

  1. Bos bir yerel port secer (sabit port cakismasi olmasin diye)
  2. Uvicorn'u ayni surecte, arka plan is parcaciginda baslatir
  3. Saglik ucu (/health) yanit verene kadar bekler
  4. PyWebView penceresini acar; PyWebView yoksa varsayilan tarayiciyi acar

Arayuz (frontend/dist) ve API ayni kokenden sunulur (bkz. ``app.main``),
bu yuzden CORS ya da ayri bir web sunucusu gerekmez.

Ortam degiskenleri (istege bagli):
    VS_DESKTOP_PORT   Sabit port kullan (varsayilan: bos port secilir)
    VS_DESKTOP_MODU   pencere  -> PyWebView penceresi (varsayilan)
                      tarayici -> varsayilan tarayiciyi ac, sunucu calisir
                      sunucu   -> arayuz acma, yalnizca sunucu (duman testi/CI)

Calistirma (gelistirme):
    .venv\\Scripts\\python.exe desktop\\masaustu.py

Paketleme:
    powershell -ExecutionPolicy Bypass -File scripts\\masaustu-paketle.ps1
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Paketlenmemis calistirmada `app` paketini (backend/) gorunur kil.
# Paketli surumde PyInstaller bunu zaten cozumlemistir.
if not getattr(sys, "frozen", False):
    _KOK = Path(__file__).resolve().parent.parent
    _BACKEND = _KOK / "backend"
    if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))

BASLIK = "Akıllı Sıcak Satış Yönetim Sistemi"
BASLATMA_ZAMAN_ASIMI = 60.0


def _akislari_onar() -> None:
    """Pencereli pakette (console=False) ``sys.stdout``/``sys.stderr`` None olur.

    Bazı kütüphaneler bunu varsayamaz — örneğin uvicorn'un günlük
    biçimlendiricisi ``sys.stdout.isatty()`` çağırır ve None akışta
    AttributeError ile düşer. None akışlar boş hedefe (os.devnull) bağlanır;
    konsollu çalıştırmada hiçbir şey değişmez.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


_akislari_onar()


def bos_port_bul() -> int:
    """İşletim sisteminden kullanılabilir bir port ister."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# Sunucu iş parçacığında oluşan hata buraya yazılır; ana iş parçacığı bunu
# kullanıcıya gösterir. Aksi hâlde hata sessizce kaybolurdu: pencereli
# pakette (console=False) stderr hiçbir yere gitmez ve kullanıcı yalnızca
# hiç açılmayan bir pencere görürdü.
_sunucu_hatasi: list[BaseException] = []


def sunucuyu_baslat(port: int) -> threading.Thread:
    """Uvicorn'u arka planda başlatır (daemon: pencere kapanınca süreç biter)."""
    import uvicorn

    from app.main import app

    yapilandirma = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    sunucu = uvicorn.Server(yapilandirma)

    def calistir() -> None:
        try:
            sunucu.run()
        except BaseException as exc:  # noqa: BLE001 — kullanıcıya raporlanır
            _sunucu_hatasi.append(exc)

    iplik = threading.Thread(target=calistir, name="uvicorn", daemon=True)
    iplik.start()
    return iplik


def hata_goster(baslik: str, mesaj: str) -> None:
    """Kullanıcıya bir hata kutusu gösterir (Windows); diğer platformlarda
    veya kutu açılamazsa stderr'e yazar.

    Pencereli pakette `print` hiçbir yere gitmez; kullanıcı ne olduğunu
    ancak bu kutudan anlayabilir.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            # MB_ICONERROR (0x10) | MB_SETFOREGROUND (0x10000)
            ctypes.windll.user32.MessageBoxW(None, mesaj, baslik, 0x10 | 0x10000)
            return
        except Exception:  # noqa: BLE001 — son çare stderr
            pass
    print(f"{baslik}: {mesaj}", file=sys.stderr)


def hata_kaydet(mesaj: str) -> None:
    """Hata ayrıntısını exe'nin yanındaki günlük dosyasına yazar.

    Pencereli pakette stderr kaybolur; mesaj kutusu da kapatılınca iz kalmaz.
    Bu dosya, kullanıcı destek istediğinde tek güvenilir kayıttır.
    """
    try:
        from app.core.config import PROJECT_ROOT

        gunluk = PROJECT_ROOT / "logs" / "masaustu-hata.log"
        gunluk.parent.mkdir(parents=True, exist_ok=True)
        zaman = time.strftime("%Y-%m-%d %H:%M:%S")
        with gunluk.open("a", encoding="utf-8") as f:
            f.write(f"[{zaman}] {mesaj}\n")
    except Exception:  # noqa: BLE001 — günlükleme asla uygulamayı düşürmemeli
        pass


def sunucuyu_bekle(port: int, zaman_asimi: float = BASLATMA_ZAMAN_ASIMI) -> bool:
    """Sağlık ucu yanıt verene kadar bekler."""
    adres = f"http://127.0.0.1:{port}/health"
    bitis = time.monotonic() + zaman_asimi
    while time.monotonic() < bitis:
        if _sunucu_hatasi:
            return False
        try:
            with urllib.request.urlopen(adres, timeout=2) as yanit:  # noqa: S310
                if yanit.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.3)
    return False


def ornek_ayar_dosyasini_kopyala() -> None:
    """Paketli modda ilk çalıştırmada `.env.example`'ı exe'nin yanına koyar.

    Kullanıcı ayarları değiştirmek isterse bu şablonu `.env` olarak
    kopyalayıp düzenler; ayrıca yedekleme servisi de bu dosyayı arşive ekler.
    """
    from app.core.config import FROZEN_RESOURCES, PROJECT_ROOT  # type: ignore[attr-defined]

    kaynak = FROZEN_RESOURCES / ".env.example"
    hedef = PROJECT_ROOT / ".env.example"
    if kaynak.is_file() and not hedef.exists():
        try:
            shutil.copyfile(kaynak, hedef)
        except OSError:
            pass  # bilgilendirme amaçlı; kopyalanamazsa uygulama yine çalışır


def surekli_bekle(iplik: threading.Thread) -> None:
    """Sunucu iş parçacığı yaşadığı sürece bekler (tarayici/sunucu modu)."""
    try:
        while iplik.is_alive():
            iplik.join(timeout=1.0)
    except KeyboardInterrupt:
        pass


def main() -> int:
    # Ayarların yüklenmesi veri klasörlerini oluşturur; yazma izni yoksa
    # BURADA patlar. Yakalanmazsa kullanıcı ham bir traceback görür.
    try:
        from app.core.config import IS_FROZEN, PROJECT_ROOT
    except Exception as exc:  # noqa: BLE001 — kullanıcıya raporlanır
        hata_goster(
            f"{BASLIK} — başlatılamadı",
            "Uygulama ayarları yüklenemedi; büyük olasılıkla veri klasörüne "
            "yazma izni yok.\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            "Çözüm: VS_DATA_DIR ortam değişkeniyle yazılabilir bir klasör "
            "gösterin.",
        )
        return 1

    if IS_FROZEN:
        ornek_ayar_dosyasini_kopyala()

    mod = os.environ.get("VS_DESKTOP_MODU", "pencere").strip().lower()
    if mod not in ("pencere", "tarayici", "sunucu"):
        mod = "pencere"

    # Pencere modu PyWebView ister; yoksa sessizce tarayıcı moduna düşülür.
    webview = None
    if mod == "pencere":
        try:
            import webview  # type: ignore[no-redef]
        except ImportError:
            webview = None
            mod = "tarayici"

    port_metni = os.environ.get("VS_DESKTOP_PORT", "").strip()
    port = int(port_metni) if port_metni.isdigit() else bos_port_bul()

    print(f"{BASLIK} başlatılıyor… (yerel port {port})")
    iplik = sunucuyu_baslat(port)

    if not sunucuyu_bekle(port):
        if _sunucu_hatasi:
            import traceback

            hata = _sunucu_hatasi[0]
            ayrinti = f"{type(hata).__name__}: {hata}"
            iz = "".join(traceback.format_exception(type(hata), hata, hata.__traceback__))
            hata_kaydet(f"Sunucu başlatılamadı.\n{iz}")
        else:
            ayrinti = f"Sunucu {BASLATMA_ZAMAN_ASIMI:.0f} saniye içinde yanıt vermedi."
            hata_kaydet(ayrinti)

        mesaj = (
            "Uygulama başlatılamadı.\n\n"
            f"{ayrinti}\n\n"
            f"Veri klasörü: {PROJECT_ROOT}\n\n"
            "Sık karşılaşılan neden: veri klasörüne yazma izni yok. "
            "VS_DATA_DIR ortam değişkeniyle yazılabilir bir klasör "
            "gösterebilirsiniz.\n\n"
            "Ayrıntılı günlük: logs\\masaustu-hata.log"
        )
        if mod == "sunucu":
            # Duman testi / CI: mesaj kutusu insansız ortamda sonsuza dek
            # bekler; günlük dosyası zaten yazıldı.
            print(mesaj, file=sys.stderr)
        else:
            hata_goster(f"{BASLIK} — başlatılamadı", mesaj)
        return 1

    adres = f"http://127.0.0.1:{port}/"

    if mod == "sunucu":
        # Duman testi / CI: arayüz açılmaz, sunucu öldürülene kadar çalışır.
        print(f"Sunucu hazır: {adres}")
        surekli_bekle(iplik)
        return 0

    if mod == "tarayici" or webview is None:
        import webbrowser

        print(f"Tarayıcı açılıyor: {adres}")
        try:
            webbrowser.open(adres)
        except Exception:  # noqa: BLE001 — adres yine de bildirildi
            hata_goster(BASLIK, f"Tarayıcı açılamadı. Elle açın: {adres}")
        surekli_bekle(iplik)
        return 0

    webview.create_window(
        BASLIK,
        adres,
        width=1440,
        height=900,
        min_size=(1024, 700),
        confirm_close=True,
    )
    # Uvicorn daemon iş parçacığındadır; pencere kapanınca süreçle birlikte biter.
    webview.start()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # Pencereli pakette (console=False) yakalanmayan bir hata hiçbir yerde
        # görünmez; süreç sessizce ölür. Son çare: günlüğe yaz, sonra yüksel.
        import traceback

        hata_kaydet("Yakalanmayan hata:\n" + traceback.format_exc())
        raise
