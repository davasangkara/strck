# app.py
# Web generator Struk Alfamart (Flask + Pillow)
# - Upload / gunakan logo.jpg
# - Pilih jumlah struk -> hasil PNG tersimpan & bisa diunduh per file atau ZIP

import os, io, random, datetime, zipfile, shutil
from pathlib import Path
from flask import Flask, request, send_file, render_template_string, redirect, url_for
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

# ===================== LAYOUT / WARNA =====================
W = 1080                 # lebar mobile portrait 9:16
PADX, PADY = 40, 36
BG   = (255, 255, 255)
FG   = (34, 34, 34)
MUT  = (122, 122, 122)
LINE = (225, 225, 225)
ACC  = (244, 163, 0)

FS_BASE  = 34
FS_SMALL = 30
FS_TINY  = 28
FS_PAID  = 34
FS_LOGO  = 60   # fallback jika logo tidak ada

COL_NAME  = 0.58
COL_QTY   = 0.08
COL_PRICE = 0.14
COL_TOTAL = 0.20

# ===================== DATA: Toko & Produk =====================
ALFAMART_STORES = [
    ("JELINDRO SAMBI K SBY", "081380746865", "SAMBIKEREP, SAMBIKEREP", "JL. JELIDRO NO 107"),
    ("CIBUBUR TRANSMART", "081298765432", "CIBUBUR, JAKARTA TIMUR", "JL. TRANSMART NO 88"),
    ("CIANJUR PERIKANAN", "082150506060", "CIANJUR, KAB. CIANJUR", "JL. PERIKANAN DARAT"),
    ("SUDIRMAN SETIABUDI", "081270003300", "SETIABUDI, JAKARTA SELATAN", "JL. JEND. SUDIRMAN NO 45"),
    ("MARGONDA DEP", "081311112222", "BEJI, DEPOK", "JL. MARGONDA RAYA NO 10"),
    ("GEDEBAGE BDG", "081222334455", "GEDEBAGE, BANDUNG", "JL. GEDEBAGE NO 12"),
    ("MERR SURABAYA", "081234567890", "RUNGKUT, SURABAYA", "JL. DR. IR. H. SOEKARNO MERR"),
    ("GAJAHMADA SMG", "081345678901", "SEMARANG TENGAH, SEMARANG", "JL. GAJAHMADA NO 21"),
    ("ANDIR PASTEUR", "081389991111", "SUKAJADI, BANDUNG", "JL. DR. DJUNDJUNAN NO 102"),
    ("SENAPELAN PEKANBARU", "081277788899", "SENAPELAN, PEKANBARU", "JL. SUDIRMAN NO 190"),
]

PRODUK_LIST = [
    ("SunCo Minyak Goreng Pouch 2 L", 43500),
    ("UBM Crackers Krim 350 g", 14500),
    ("L-Men Protein Bar Cokelat 22 g", 9900),
    ("SilverQueen Cokelat Susu Cashew 55 g", 17500),
    ("NyamNyam Fantasy Stick Stroberi 25 g", 9500),
    ("Dua Kelinci Tic Tac Pilus Mix 80 g", 7400),
    ("Dua Kelinci Tic Tac Pilus Sapi Panggang 80 g", 7400),
    ("Dua Kelinci Tic Tac Pilus Mie Goreng 80 g", 7400),
    ("Dua Kelinci Tic Tac Pilus Rumput Laut 80 g", 6100),
    ("Dua Kelinci Tic Tac Pilus Pedas 80 g", 6100),
    ("Dua Kelinci Tic Tac Pilus Ayam Bawang 80 g", 6800),
    ("Dua Kelinci Tic Tac Pilus Original 80 g", 6400),
]
TIC_TAC_INDEXES = [i for i, (nm, _) in enumerate(PRODUK_LIST) if "Tic Tac" in nm]

# ===================== UTIL =====================
def rupiah(n: int) -> str:
    return f"{int(round(n)):,.0f}"

HARI  = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
BULAN = ["Januari","Februari","Maret","April","Mei","Juni","Juli",
         "Agustus","September","Oktober","November","Desember"]

def tanggal_indo(dt: datetime.datetime) -> str:
    return f"{HARI[dt.weekday()]}, {dt.day:02d} {BULAN[dt.month-1]} {dt.year}"

def pickup_window(dt: datetime.datetime) -> str:
    start = dt.replace(minute=0, second=0, microsecond=0)
    end   = start + datetime.timedelta(hours=2)
    return f"{start:%H}:00 - {end:%H}:00"

def gen_ref(dt: datetime.datetime) -> str:
    huruf = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6))
    return f"S-{dt.strftime('%y%m%d')}-{huruf}"

def load_font(size, prefer_bold=False):
    cands = [
        ("Inter-Medium.ttf", True),
        ("Inter-Regular.ttf", False),
        ("Arial.ttf", False), ("arial.ttf", False),
        ("DejaVuSans.ttf", False), ("DejaVuSans-Bold.ttf", True),
    ]
    if prefer_bold:
        for name, is_bold in cands:
            if not is_bold: 
                continue
            try:
                return ImageFont.truetype(name, size)
            except:
                pass
    for name, _ in cands:
        try:
            return ImageFont.truetype(name, size)
        except:
            continue
    return ImageFont.load_default()

def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int):
    if not text:
        return [""]
    words, line, lines = text.split(), "", []
    for w in words:
        t = (line + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            line = t
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines

# ===================== GARIS =====================
def dashed(draw, x1, x2, y, dash=30, gap=16, thick=2, color=LINE):
    x = x1
    while x < x2:
        draw.line((x, y, min(x+dash, x2), y), fill=color, width=thick)
        x += dash + gap

def dashed_item(draw, x1, x2, y):
    dashed(draw, x1, x2, y, dash=20, gap=14, thick=2)

def equals_double(draw, x1, x2, y, seg=18, gap=16, thick=2, sep=8, color=LINE):
    x = x1
    while x < x2:
        draw.line((x, y, min(x+seg, x2), y), fill=color, width=thick)
        x += seg + gap
    yy = y + sep
    x = x1
    while x < x2:
        draw.line((x, yy, min(x+seg, x2), yy), fill=color, width=thick)
        x += seg + gap
    return yy

# ===================== RENDER STRUK (PIL) =====================
def render_receipt_png(store_tuple, keranjang, diskon, voucher, dt, out_path, logo_bytes=None):
    CABANG, NO_TOKO, KOTA, ALAMAT3 = store_tuple
    TOKO = "Alfamart"

    f_base  = load_font(FS_BASE)
    f_small = load_font(FS_SMALL)
    f_tiny  = load_font(FS_TINY)
    f_paid  = load_font(FS_PAID)
    f_logo  = load_font(FS_LOGO, prefer_bold=True)

    Htmp = 5000
    img = Image.new("RGB", (W, Htmp), BG)
    d = ImageDraw.Draw(img)

    x1, x2 = PADX, W - PADX
    y = PADY

    # ===== LOGO =====
    logo = None
    if logo_bytes:
        try:
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        except:
            logo = None
    else:
        if os.path.exists("logo.jpg"):
            try:
                logo = Image.open("img/logo.jpg").convert("RGBA")
            except:
                logo = None

    if logo:
        max_w = int(W * 0.42)
        ratio = max_w / logo.width
        new_size = (int(logo.width * ratio), int(logo.height * ratio))
        logo = logo.resize(new_size, Image.LANCZOS)
        img.paste(logo, ((W - logo.width)//2, y), logo)
        y += logo.height + 28
    else:
        text_w = d.textlength(TOKO, font=f_logo)
        d.text(((W - text_w)//2, y), TOKO, fill=FG, font=f_logo)
        y += f_logo.size + 28

    # ===== Pickup at =====
    d.text((x1, y), "Pickup at :", fill=FG, font=f_base)
    alamat1_like = "JL. JELIDRO NO 107 - SAMBIKEREP"  # tampilan kanan baris 2 (mirip contoh)
    d.text((x2 - d.textlength(CABANG, font=f_small), y), CABANG, fill=MUT, font=f_small)
    y += f_small.size + 2
    d.text((x2 - d.textlength(alamat1_like, font=f_small), y), alamat1_like, fill=MUT, font=f_small)
    y += f_small.size + 14

    dashed(d, x1, x2, y); y += 18

    # ===== Tanggal + Slot =====
    tgl  = tanggal_indo(dt)
    slot = pickup_window(dt)
    d.text((x2 - d.textlength(tgl, font=f_small), y), tgl,  fill=MUT, font=f_small)
    y += f_small.size + 2
    d.text((x2 - d.textlength(slot, font=f_small), y), slot, fill=MUT, font=f_small)
    y += f_small.size + 14

    dashed(d, x1, x2, y); y += 20

    # ===== Status Order =====
    d.text((x1, y), "Status Order :", fill=FG, font=f_base)
    # (text, position, fill, font) -> urutan argumen benar
    d.text((x2 - d.textlength("Selesai", font=f_base), y), "Selesai", fill=ACC, font=f_base)
    y += f_base.size + 24

    # ===== Blok tengah (center muted) =====
    for ln in (CABANG, NO_TOKO, KOTA, ALAMAT3):
        w = d.textlength(ln, font=f_small)
        d.text((x1 + (x2 - x1 - w)//2, y), ln, fill=MUT, font=f_small)
        y += f_small.size + 6

    y += 4
    yb = equals_double(d, x1, x2, y, seg=18, gap=16, thick=2, sep=8)
    y = yb + 18

    # ===== Ref =====
    ref = gen_ref(dt)
    d.text((x1, y), f"Ref. {ref}", fill=FG, font=f_base)
    y += f_base.size + 12

    yb = equals_double(d, x1, x2, y, seg=18, gap=16, thick=2, sep=8)
    y = yb + 22

    # ===== Items =====
    name_w  = int((x2 - x1) * COL_NAME)
    qty_w   = int((x2 - x1) * COL_QTY)
    price_w = int((x2 - x1) * COL_PRICE)
    total_w = int((x2 - x1) * COL_TOTAL)

    subtotal, total_qty = 0, 0
    for nama, qty, harga in keranjang:
        line_total = qty * harga
        subtotal += line_total
        total_qty += qty

        nm_lines = wrap(d, nama, f_base, name_w)
        d.text((x1, y), nm_lines[0], fill=FG, font=f_base)

        t = str(qty)
        d.text((x1 + name_w + qty_w - d.textlength(t, font=f_base) + 20, y), t, fill=FG, font=f_base)

        t = rupiah(harga)
        d.text((x1 + name_w + qty_w + price_w - d.textlength(t, font=f_base) + 24, y), t, fill=FG, font=f_base)

        t = rupiah(line_total)
        d.text((x2 - d.textlength(t, font=f_base), y), t, fill=FG, font=f_base)

        y += f_base.size + 8
        for ln in nm_lines[1:]:
            d.text((x1, y), ln, fill=MUT, font=f_small)
            y += f_small.size + 4

        y += 2
        dashed_item(d, x1, x2, y)
        y += 18

    # ===== Ringkasan =====
    def row(lbl, qty, val, neg=False):
        nonlocal y
        d.text((x1, y), lbl, fill=FG, font=f_base)
        if qty is not None:
            t = str(qty)
            d.text((x1 + name_w + qty_w - d.textlength(t, font=f_base) + 20, y), t, fill=FG, font=f_base)
        t = rupiah(val)
        if neg:
            t = f"({t})"
        d.text((x2 - d.textlength(t, font=f_base), y), t, fill=FG, font=f_base)
        y += f_base.size + 10

    diskon  = int(diskon or 0)
    voucher = int(voucher or 0)
    ONGKIR  = 0
    total   = subtotal - diskon - voucher + ONGKIR

    row("Subtotal", total_qty, subtotal, neg=False)
    row("Total Diskon", None, diskon, neg=True)
    row("Voucher", None, voucher, neg=True)
    row("Biaya Pengiriman", None, ONGKIR, neg=False)
    row("Total", None, total, neg=False)

    d.text((x1, y), "*Harga yang tertera sudah termasuk PPN", fill=FG, font=f_tiny)
    y += f_tiny.size + 16

    dashed(d, x1, x2, y); y += 22
    paid = "L U N A S"
    d.text((x1 + (x2 - x1 - d.textlength(paid, font=f_paid))//2, y), paid, fill=(88, 88, 88), font=f_paid)
    y += f_paid.size + 12
    dashed(d, x1, x2, y); y += 22

    tgl_kecil = f"Tgl. {dt.strftime('%d-%m-%Y %H:%M:%S')}"
    d.text((x1 + (x2 - x1 - d.textlength(tgl_kecil, font=f_small))//2, y), tgl_kecil, fill=MUT, font=f_small)
    y += f_small.size + 18

    dashed(d, x1, x2, y); y += 22

    for ln in ("Kritik & Saran: 1500959", "Email: alfacare@sat.co.id"):
        d.text((x1 + (x2 - x1 - d.textlength(ln, font=f_small))//2, y), ln, fill=MUT, font=f_small)
        y += f_small.size + 12

    dashed(d, x1, x2, y); y += 20

    out_img = img.crop((0, 0, W, y + PADY))
    out_img.save(out_path, "PNG")
    return out_path

# ===================== DATA GENERATOR =====================
def pick_store_random():
    return random.choice(ALFAMART_STORES)

def gen_items_prioritize_tictac():
    items = []
    n_tt = random.randint(2, 4)  # lebih banyak Tic Tac
    tt_choices = random.sample(TIC_TAC_INDEXES, min(n_tt, len(TIC_TAC_INDEXES)))
    for idx in tt_choices:
        nm, pr = PRODUK_LIST[idx]
        qty = random.randint(1, 6)
        items.append((nm, qty, pr))
    others_pool = [i for i in range(len(PRODUK_LIST)) if i not in tt_choices]
    for _ in range(random.randint(0, 2)):
        idx = random.choice(others_pool)
        nm, pr = PRODUK_LIST[idx]
        qty = random.randint(1, 4)
        items.append((nm, qty, pr))
    return items

# ===================== ROUTES =====================
TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Generator Struk Alfamart</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;margin:0;background:#f6f7f8;color:#222}
    .wrap{max-width:920px;margin:0 auto;padding:24px}
    .card{background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 1px 6px rgba(0,0,0,.06)}
    h1{margin:0 0 10px}
    label{display:block;margin:10px 0 6px;font-weight:600}
    input[type="number"],input[type="file"]{width:100%;padding:.65rem;border:1px solid #d7d7d7;border-radius:10px;font:inherit}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    .row>*{flex:1 1 220px}
    .btn{background:#111;color:#fff;border:0;padding:.7rem 1.1rem;border-radius:999px;cursor:pointer}
    .btn.secondary{background:#eee;color:#111}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:14px}
    .thumb{background:#fff;border-radius:12px;padding:10px;text-align:center;box-shadow:0 1px 6px rgba(0,0,0,.06)}
    .thumb img{max-width:100%;height:auto;border-radius:8px}
    .muted{color:#777}
    .bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:12px}
    a.dl{display:inline-block;padding:.55rem .9rem;border-radius:999px;background:#0a7;color:#fff;text-decoration:none}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Generator Struk Alfamart (PNG)</h1>
      <form method="post" action="{{ url_for('generate') }}" enctype="multipart/form-data">
        <div class="row">
          <div>
            <label>Jumlah struk</label>
            <input type="number" name="count" value="10" min="1" max="200" required>
          </div>
          <div>
            <label>Logo (opsional, .jpg/.png)</label>
            <input type="file" name="logo">
            <div class="muted">Jika kosong, pakai <code>logo.jpg</code> di server (jika ada).</div>
          </div>
        </div>
        <div class="bar">
          <button class="btn" type="submit">Generate</button>
          <a class="btn secondary" href="{{ url_for('index') }}">Reset</a>
        </div>
      </form>
    </div>

    {% if folder %}
    <div class="card" style="margin-top:16px">
      <h2 style="margin:0 0 8px">Hasil: {{ folder_name }}</h2>
      <div class="bar">
        <a class="dl" href="{{ url_for('download_zip', folder=folder_name) }}">Download ZIP</a>
        <div class="muted">Total file: {{ files|length }}</div>
      </div>
      <div class="grid">
        {% for f in files %}
        <div class="thumb">
          <div class="muted" style="margin-bottom:6px">{{ f }}</div>
          <img src="{{ url_for('get_file', folder=folder_name, filename=f) }}" alt="{{ f }}">
          <div style="margin-top:8px">
            <a class="dl" href="{{ url_for('get_file', folder=folder_name, filename=f) }}">Unduh</a>
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}
  </div>
</body>
</html>
"""
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_ROOT", "struk_web"))


@app.route("/", methods=["GET"])
def index():
    return render_template_string(TEMPLATE, folder=False, folder_name=None, files=[])

@app.route("/generate", methods=["POST"])
def generate():
    # jumlah
    try:
        count = int(request.form.get("count", "1"))
    except:
        count = 1
    count = max(1, min(count, 200))

    # logo (opsional)
    logo_bytes = None
    file = request.files.get("logo")
    if file and file.filename:
        logo_bytes = file.read()

    # folder output time-based
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_ROOT / f"batch_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i in range(1, count+1):
        store = random.choice(ALFAMART_STORES)
        keranjang = gen_items_prioritize_tictac()
        # diskon/voucher acak kecil biar realistis
        subtotal = sum(q*pr for _, q, pr in keranjang)
        diskon  = random.choice([0, 0, 0, 27600, 15000]) if subtotal > 50000 else 0
        voucher = random.choice([0, 0, 50000]) if subtotal > 200000 else 0
        # waktu sesuai sekarang (+offset menit kecil agar unik), slot = 2 jam
        dt = datetime.datetime.now() + datetime.timedelta(minutes=random.randint(0, 4))
        out_path = out_dir / f"struk_{i:02d}.png"
        render_receipt_png(store, keranjang, diskon, voucher, dt, str(out_path), logo_bytes=logo_bytes)
        files.append(out_path.name)

    return render_template_string(
        TEMPLATE,
        folder=True,
        folder_name=out_dir.name,
        files=files
    )

@app.route("/file/<folder>/<filename>")
def get_file(folder, filename):
    file_path = OUTPUT_ROOT / folder / filename
    if not file_path.exists():
        return "File not found", 404
    return send_file(str(file_path), mimetype="image/png", as_attachment=False)

@app.route("/zip/<folder>")
def download_zip(folder):
    dir_path = OUTPUT_ROOT / folder
    if not dir_path.exists():
        return "Folder not found", 404
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(dir_path.glob("*.png")):
            zf.write(p, arcname=p.name)
    mem.seek(0)
    return send_file(mem, mimetype="application/zip", as_attachment=True, download_name=f"{folder}.zip")

# Opsional: bersihkan batch lama
@app.route("/cleanup", methods=["POST"])
def cleanup():
    keep_last = int(request.form.get("keep_last", "3"))
    batches = sorted(OUTPUT_ROOT.glob("batch_*"))
    if len(batches) > keep_last:
        for p in batches[:-keep_last]:
            shutil.rmtree(p, ignore_errors=True)
    return redirect(url_for("index"))

if __name__ == "__main__":
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
