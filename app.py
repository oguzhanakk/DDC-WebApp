import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, after_this_request, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB max upload

# Repo root is one level above this file (DDC_WebApp/../)
REPO_ROOT = Path(__file__).parent.parent

CONVERTERS = {
    "revit": {
        "label": "Revit → XLSX / DAE",
        "exe": REPO_ROOT / "DDC_WINDOWS_Converters/DDC_CONVERTER_REVIT/RvtExporter.exe",
        "extensions": [".rvt", ".rfa"],
        "output_exts": ["xlsx", "dae", "pdf"],
    },
    "dwg": {
        "label": "DWG → XLSX / PDF",
        "exe": REPO_ROOT / "DDC_WINDOWS_Converters/DDC_CONVERTER_DWG/DwgExporter.exe",
        "extensions": [".dwg"],
        "output_exts": ["xlsx", "pdf"],
    },
    "ifc": {
        "label": "IFC → XLSX / DAE",
        "exe": REPO_ROOT / "DDC_WINDOWS_Converters/DDC_CONVERTER_IFC/IfcExporter.exe",
        "extensions": [".ifc"],
        "output_exts": ["xlsx", "dae"],
    },
    "dgn": {
        "label": "DGN → XLSX",
        "exe": REPO_ROOT / "DDC_WINDOWS_Converters/DDC_CONVERTER_DGN/DgnExporter.exe",
        "extensions": [".dgn"],
        "output_exts": ["xlsx"],
    },
    "rvt2ifc": {
        "label": "Revit → IFC",
        "exe": REPO_ROOT / "DDC_WINDOWS_Converters/DDC_CONVERTER_Revit2IFC/DDC_REVIT2IFC_CONVERTER/RVT2IFCconverter.exe",
        "extensions": [".rvt", ".rfa"],
        "output_exts": ["ifc", "ifcxml", "ifczip"],
    },
}


def build_command(
    converter_type: str,
    exe_path: Path,
    input_path: Path,
    temp_dir: Path,
    form: dict,
) -> list:
    stem = input_path.stem
    cmd = [str(exe_path), str(input_path)]

    if converter_type == "revit":
        no_xlsx    = bool(form.get("no_xlsx"))
        no_collada = bool(form.get("no_collada"))

        # Positional output paths (required before mode/flags)
        out_dae  = str(temp_dir / f"{stem}.dae")
        out_xlsx = str(temp_dir / f"{stem}.xlsx")
        if not no_collada:
            cmd.append(out_dae)
        if not no_xlsx:
            cmd.append(out_xlsx)

        export_mode = form.get("export_mode", "standard")
        if export_mode and export_mode != "standard":
            cmd.append(export_mode)

        for flag in ["bbox", "room", "schedule", "sheets2pdf"]:
            if form.get(flag):
                cmd.append(flag)

        if no_xlsx:
            cmd.append("-no-xlsx")
        if no_collada:
            cmd.append("-no-collada")

    elif converter_type == "rvt2ifc":
        out_ifc = str(temp_dir / f"{stem}.ifc")
        cmd.append(out_ifc)

        preset = form.get("preset", "standard")
        if preset and preset != "standard":
            cmd.append(f"preset={preset}")

        config = (form.get("config") or "").strip()
        if config:
            cmd.append(f'config="{config}"')

    # DWG / IFC / DGN: no explicit output path needed.
    # The exe writes output next to the input file (temp_dir).

    return cmd


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    converter_type = request.form.get("converter", "").strip()
    if converter_type not in CONVERTERS:
        return jsonify({"error": "Geçersiz dönüştürücü tipi."}), 400

    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "Dosya seçilmedi."}), 400

    uploaded = request.files["file"]
    original_name = secure_filename(uploaded.filename)
    ext = Path(original_name).suffix.lower()
    converter = CONVERTERS[converter_type]

    if ext not in converter["extensions"]:
        allowed = ", ".join(converter["extensions"])
        return jsonify({"error": f"Bu dönüştürücü {allowed} uzantılı dosya kabul eder. Yüklenen: {ext}"}), 400

    exe_path = converter["exe"]
    if not exe_path.exists():
        return jsonify({
            "error": f"Converter bulunamadı: {exe_path.name}",
            "details": f"Beklenen yol: {exe_path}"
        }), 500

    temp_dir = Path(tempfile.mkdtemp(prefix="ddc_"))

    @after_this_request
    def cleanup(response):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return response

    try:
        input_path = temp_dir / original_name
        uploaded.save(str(input_path))

        cmd = build_command(converter_type, exe_path, input_path, temp_dir, request.form)

        # exe kendi klasöründen çalıştırılmalı — DLL'ler (Qt6, ODA) orada
        exe_cwd = str(exe_path.parent)

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,  # 10 dakika
            cwd=exe_cwd,
        )

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        if proc.returncode != 0:
            return jsonify({
                "error": "Dönüştürme başarısız oldu.",
                "details": (stderr or stdout).strip() or f"Exit code: {proc.returncode}",
            }), 500

        # Çıktı dosyalarını topla: temp_dir içindeki tüm beklenen uzantılar
        stem = input_path.stem
        output_files = []
        for out_ext in converter["output_exts"]:
            for pattern in [f"*.{out_ext}", f"*.{out_ext.upper()}", f"{stem}*.{out_ext}"]:
                output_files += list(temp_dir.glob(pattern))

        # Input dosyasını dışarıda bırak, tekrarları temizle
        output_files = [
            f for f in output_files
            if f.resolve() != input_path.resolve() and f.exists()
        ]
        output_files = list({f.resolve(): f for f in output_files}.values())

        if not output_files:
            return jsonify({
                "error": "Dönüştürme tamamlandı ancak çıktı dosyası bulunamadı.",
                "details": (stdout or stderr).strip(),
            }), 500

        # Tek dosya → direkt gönder; çoklu dosya → zip
        if len(output_files) == 1:
            data = output_files[0].read_bytes()
            return send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name=output_files[0].name,
                mimetype="application/octet-stream",
            )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in output_files:
                zf.write(f, f.name)
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"{stem}_converted.zip",
            mimetype="application/zip",
        )

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Dönüştürme zaman aşımına uğradı (10 dakika)."}), 500
    except Exception as exc:
        return jsonify({"error": "Sunucu hatası.", "details": str(exc)}), 500


@app.route("/check_converters")
def check_converters():
    """Hangi converter exe'lerinin mevcut olduğunu kontrol et."""
    status = {}
    for key, info in CONVERTERS.items():
        status[key] = {
            "label": info["label"],
            "exe": str(info["exe"]),
            "found": info["exe"].exists(),
        }
    return jsonify(status)


if __name__ == "__main__":
    print("\n🚀 DDC CAD2DATA Web Converter başlatılıyor...")
    print(f"   Repo root : {REPO_ROOT}")
    print("   Adres     : http://localhost:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
