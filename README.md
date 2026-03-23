# DDC CAD2DATA Web Converter

Revit, DWG, IFC ve DGN dosyalarını Excel'e dönüştüren web arayüzü.

## Gereksinimler

- Windows 10 / 11
- [Python 3.10+](https://python.org/downloads) — kurulumda **"Add to PATH"** seçeneğini işaretle

## Kurulum

**1. Bu repoyu klonla:**
```cmd
git clone https://github.com/oguzhanakk/DDC-WebApp.git
```

**2. Converter klasörünü yanına koy:**

Klasör yapısı şöyle olmalı:

```
C:\Projects\
├── DDC-WebApp\              ← bu repo (git clone ile geldi)
│   ├── app.py
│   ├── requirements.txt
│   └── templates\
└── DDC_WINDOWS_Converters\  ← converter exe'leri buraya (ayrıca temin edilir)
    ├── DDC_CONVERTER_REVIT\
    ├── DDC_CONVERTER_DWG\
    ├── DDC_CONVERTER_IFC\
    ├── DDC_CONVERTER_DGN\
    └── DDC_CONVERTER_Revit2IFC\
```

> `DDC-WebApp` ve `DDC_WINDOWS_Converters` klasörleri **aynı dizinde** olmalı.

**3. Bağımlılıkları kur ve çalıştır:**
```cmd
cd DDC-WebApp
pip install -r requirements.txt
python app.py
```

Tarayıcıda aç: **http://localhost:5000**

## Kullanım

1. Dönüştürücü seç (Revit, DWG, IFC, DGN…)
2. Dosyayı sürükle-bırak ya da tıklayarak seç
3. **Dönüştür & İndir** butonuna bas
4. Çıktı dosyası otomatik indirilir

Anasayfada **Converter durumu** satırı hangi exe'lerin bulunduğunu gösterir.
