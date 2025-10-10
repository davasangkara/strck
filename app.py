import os
import io
import random
import datetime as dt
from pathlib import Path
from flask import Flask, render_template, request, send_from_directory, redirect, url_for
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ================== KONFIG & DATA ==================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_BASE = STATIC_DIR / "struk"
LOGO_PATH = STATIC_DIR / "logo.jpg"  # pastikan file ini ada

# Kanvas 9:16 (mobile)
CANVAS_W = 1080
CANVAS_H = 1920

# Warna & spacing
BG   = (255, 255, 255)
FG   = (34, 34, 34)
MUT  = (122, 122, 122)
LINE = (225, 225, 225)
ACC  = (244, 163, 0)

PADX, PADY = 40, 36

# Font fallback order (silakan tambahkan TTF ke /static/fonts bila punya)
FONT_CANDIDATES = [
    ("static/fonts/Inter-Regular.ttf", False),
    ("static/fonts/Inter-Medium.ttf", True),
    ("static/fonts/Arial.ttf", False),
    ("static/fonts/arial.ttf", False),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", False),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", True),
]

FS_BASE  = 42   # body utama
FS_SMALL = 36   # teks kecil/muted
FS_TINY  = 32   # catatan PPN
FS_PAID  = 42   # "L U N A S"

# Proporsi kolom tabel
COL_NAME  = 0.58
COL_QTY   = 0.08
COL_PRICE = 0.14
COL_TOTAL = 0.20

# Contoh alamat toko Alfamart (acak)
ALFAMART_STORES = [
    ("ALFAMART", "GEDONG MENENG RAJABASA", "0721-777999",
     "JL ZAINAL ABIDIN PAGAR ALAM NO 15", "RAJABASA, BANDAR LAMPUNG", "BANDAR LAMPUNG"),
    ("ALFAMART", "CIPETE RAYA", "021-7288888",
     "JL CIPETE RAYA NO 10", "CIPETE, JAKARTA SELATAN", "DKI JAKARTA"),
    ("ALFAMART", "TAMAN GALAXY", "021-88997766",
     "JL BOULEVARD TAMAN GALAXY RAYA", "BEKASI SELATAN, BEKASI", "JAWA BARAT"),
    ("ALFAMART", "SURYAKENCANA", "0251-838383",
     "JL SURYAKENCANA NO 45", "BOGOR TENGAH, BOGOR", "JAWA BARAT"),
    ("ALFAMART", "NGINDEN INTAN", "031-555777",
     "JL NGINDEN INTAN BARAT", "SUKOLILO, SURABAYA", "JAWA TIMUR"),
    ("ALFAMART", "PANDANARAN", "024-7605050",
     "JL PANDANARAN NO 35", "SEMARANG TENGAH, SEMARANG", "JAWA TENGAH"),
    ("ALFAMART", "DENPASAR TEUKU UMAR", "0361-220220",
     "JL TEUKU UMAR NO 100", "DENPASAR BARAT, DENPASAR", "BALI"),
]

# Produk – prioritas Tic Tac + lainnya acak
PRODUCTS_TICTAC = [
    ("Dua Kelinci Tic Tac Pilus Mix 80 g", 7400),
    ("Dua Kelinci Tic Tac Pilus Sapi Panggang 80 g", 7400),
    ("Dua Kelinci Tic Tac Pilus Mie Goreng 80 g", 7400),
    ("Dua Kelinci Tic Tac Pilus Rumput Laut 80 g", 6100),
    ("Dua Kelinci Tic Tac Pilus Pedas 80 g", 6100),
    ("Dua Kelinci Tic Tac Pilus Ayam Bawang 80 g", 6800),
    ("Dua Kelinci Tic Tac Pilus Original 80 g", 6400),
]
PRODUCTS_OTHER = [
    ("SunCo Minyak Goreng Pouch 2 L", 43500),
    ("UBM Crackers Krim 350 g", 14500),
    ("L-Men Protein Bar Cokelat 22 g", 9900),
    ("SilverQueen Cokelat Susu Cashew 55 g", 17500),
    ("NyamNyam Fantasy Stick Stroberi 25 g", 9500),
    ("Indomie Goreng 85 g", 3800),
    ("Teh Pucuk Harum 350 ml", 4500),
    ("Aqua Botol 600 ml", 4500),
]

# ================== UTIL ==================
def rupiah(n: int) -> str:
    # Format 43,500 style (koma internasional akan dipakai titik oleh browser saat render)
    return f"{int(round(n)):,.0f}"

def tanggal_indo(d: dt.datetime) -> str:
    hari  = ["Minggu","Senin","Selasa","Rabu","Kamis","Jumat","Sabtu"]
    bulan = ["Januari","Februari","Maret","April","Mei","Juni","Juli",
             "Agustus","September","Oktober","November","Desember"]
    return f"{hari[d.weekday()]}, {d.day:02d} {bulan[d.month-1]} {d.year}"

def gen_ref(now: dt.datetime) -> str:
    huruf = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6))
    return f"S-{now.strftime('%y%m%d')}-{huruf}"

def load_font(size: int, prefer_bold=False) -> ImageFont.FreeTypeFont:
    for path, is_bold in FONT_CANDIDATES:
        if prefer_bold and not is_bold:
            continue
        p = BASE_DIR / path if not path.startswith("/") else Path(path)
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()

def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int):
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

# Garis
def dashed(draw, x1, x2, y, dash=50, gap=24, thick=2, color=LINE):
    x = x1
    while x < x2:
        draw.line((x, y, min(x + dash, x2), y), fill=color, width=thick)
        x += dash + gap

def dashed_item(draw, x1, x2, y):
    dashed(draw, x1, x2, y, dash=28, gap=18, thick=2)

def equals_double(draw, x1, x2, y, seg=28, gap=20, thick=2, sep=10, color=LINE):
    # atas
    x = x1
    while x < x2:
        draw.line((x, y, min(x + seg, x2), y), fill=color, width=thick)
        x += seg + gap
    # bawah
    yy = y + sep
    x = x1
    while x < x2:
        draw.line((x, yy, min(x + seg, x2), yy), fill=color, width=thick)
        x += seg + gap
    return yy

# ================== RENDER RECEIPT ==================
def render_receipt_png(store, items, diskon, voucher, now_dt, out_path, logo_path):
    TOKO, CABANG, NO_TOKO, ALAMAT1, KOTA, ALAMAT3 = store
    # Fonts
    f_base  = load_font(FS_BASE)
    f_small = load_font(FS_SMALL)
    f_tiny  = load_font(FS_TINY)
    f_paid  = load_font(FS_PAID)
    # Canvas
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    d = ImageDraw.Draw(img)

    x1, x2 = PADX, CANVAS_W - PADX
    y = PADY

    # ===== LOGO =====
    if Path(logo_path).exists():
        # Fit logo ke lebar maksimum 520 px, proporsional
        logo = Image.open(logo_path).convert("RGBA")
        max_w = int(CANVAS_W * 0.5)
        scale = min(max_w / logo.width, 1.0)
        lw = int(logo.width * scale)
        lh = int(logo.height * scale)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        img.paste(logo, (x1 + (x2 - x1 - lw) // 2, y), logo)
        y += lh + 16
    else:
        # fallback teks
        title = "Alfamart"
        f_logo = load_font(48, prefer_bold=True)
        d.text((x1 + (x2 - x1 - d.textlength(title, font=f_logo)) // 2, y), title, fill=FG, font=f_logo)
        y += 70

    # ===== Pickup + lokasi kanan (dua baris) =====
    d.text((x1, y), "Pickup at :", fill=FG, font=f_base)
    right = CABANG
    d.text((x2 - d.textlength(right, font=f_small), y), right, fill=MUT, font=f_small)
    y += f_small.size + 4
    right2 = ALAMAT1
    d.text((x2 - d.textlength(right2, font=f_small), y), right2, fill=MUT, font=f_small)
    y += f_small.size + 12

    dashed(d, x1, x2, y); y += 16

    # ===== Tanggal + slot (kanan) =====
    tgl  = tanggal_indo(now_dt)
    start_h = max(now_dt.hour, 8)
    end_h = min(start_h + 2, 23)
    slot = f"{start_h:02d}:00 - {end_h:02d}:00"
    d.text((x2 - d.textlength(tgl, font=f_small), y), tgl, fill=MUT, font=f_small)
    y += f_small.size + 4
    d.text((x2 - d.textlength(slot, font=f_small), y), slot, fill=MUT, font=f_small)
    y += f_small.size + 12

    dashed(d, x1, x2, y); y += 18

    # ===== Status Order =====
    d.text((x1, y), "Status Order :", fill=FG, font=f_base)
    selesai_w = d.textlength("Selesai", font=f_base)
    d.text((x2 - selesai_w, y), "Selesai", fill=ACC, font=f_base)
    y += f_base.size + 20

    # ===== Store block (center muted) =====
    for ln in (CABANG, NO_TOKO, KOTA, ALAMAT3):
        w = d.textlength(ln, font=f_small)
        d.text((x1 + (x2 - x1 - w) // 2, y), ln, fill=MUT, font=f_small)
        y += f_small.size + 6

    # ===== Garis == atas Ref =====
    y += 10
    yb = equals_double(d, x1, x2, y, seg=28, gap=20, thick=2, sep=10)
    y = yb + 14

    # ===== Ref =====
    ref = gen_ref(now_dt)
    d.text((x1, y), f"Ref. {ref}", fill=FG, font=f_base)
    y += f_base.size + 10

    # ===== Garis == bawah Ref =====
    yb = equals_double(d, x1, x2, y, seg=28, gap=20, thick=2, sep=10)
    y = yb + 20

    # ===== Items =====
    name_w  = int((x2 - x1) * COL_NAME)
    qty_w   = int((x2 - x1) * COL_QTY)
    price_w = int((x2 - x1) * COL_PRICE)
    total_w = int((x2 - x1) * COL_TOTAL)

    subtotal, total_qty = 0, 0
    for nama, qty, harga in items:
        line_total = qty * harga
        subtotal += line_total
        total_qty += qty

        nm_lines = wrap(d, nama, f_base, name_w)
        d.text((x1, y), nm_lines[0], fill=FG, font=f_base)

        t = str(qty)
        d.text((x1 + name_w + qty_w - d.textlength(t, font=f_base) + 10, y), t, fill=FG, font=f_base)

        t = rupiah(harga)
        d.text((x1 + name_w + qty_w + price_w - d.textlength(t, font=f_base) + 12, y), t, fill=FG, font=f_base)

        t = rupiah(line_total)
        d.text((x2 - d.textlength(t, font=f_base), y), t, fill=FG, font=f_base)

        y += f_base.size + 8
        for ln in nm_lines[1:]:
            d.text((x1, y), ln, fill=MUT, font=f_small)
            y += f_small.size + 4

        dashed_item(d, x1, x2, y); y += 16

    # ===== Ringkasan =====
    def row(lbl, qty, val, neg=False):
        nonlocal y
        d.text((x1, y), lbl, fill=FG, font=f_base)
        if qty is not None:
            t = str(qty)
            d.text((x1 + name_w + qty_w - d.textlength(t, font=f_base) + 10, y), t, fill=FG, font=f_base)
        t = rupiah(val)
        if neg:
            t = f"({t})"
        d.text((x2 - d.textlength(t, font=f_base), y), t, fill=FG, font=f_base)
        y += f_base.size + 10

    diskon  = int(diskon or 0)
    voucher = int(voucher or 0)
    ongkir  = 0
    total   = subtotal - diskon - voucher + ongkir

    row("Subtotal", total_qty, subtotal, neg=False)
    row("Total Diskon", None, diskon, neg=True)
    row("Voucher", None, voucher, neg=True)
    row("Biaya Pengiriman", None, ongkir, neg=False)
    row("Total", None, total, neg=False)

    # ===== Catatan PPN =====
    d.text((x1, y), "*Harga yang tertera sudah termasuk PPN", fill=FG, font=f_tiny)
    y += f_tiny.size + 14

    # ===== L U N A S + garis atas-bawah =====
    dashed(d, x1, x2, y); y += 20
    paid = "L U N A S"
    d.text((x1 + (x2 - x1 - d.textlength(paid, font=f_paid)) // 2, y), paid, fill=(88, 88, 88), font=f_paid)
    y += f_paid.size + 12
    dashed(d, x1, x2, y); y += 22

    # ===== Tanggal kecil center =====
    tgl_kecil = f"Tgl. {now_dt.strftime('%d-%m-%Y %H:%M:%S')}"
    d.text((x1 + (x2 - x1 - d.textlength(tgl_kecil, font=f_small)) // 2, y), tgl_kecil, fill=MUT, font=f_small)
    y += f_small.size + 16

    dashed(d, x1, x2, y); y += 20

    for ln in ("Kritik & Saran: 1500959", "Email: alfacare@sat.co.id"):
        d.text((x1 + (x2 - x1 - d.textlength(ln, font=f_small)) // 2, y), ln, fill=MUT, font=f_small)
        y += f_small.size + 10

    dashed(d, x1, x2, y); y += 20

    # Crop vertikal agar rapat, tetap kanvas 9:16 dengan white-space bawah
    # Kita ambil area terpakai sampai y, lalu paste ke kanvas final 1080×1920
    content = img.crop((0, 0, CANVAS_W, min(y + PADY, CANVAS_H)))
    final_img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    # center vertical jika tinggi konten < canvas
    top = (CANVAS_H - content.height) // 8  # agak naik (biar mirip SS)
    final_img.paste(content, (0, max(0, top)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(str(out_path), "PNG")
    return str(out_path)

# ================== GENERATOR LOGIKA ==================
def pick_random_store():
    toko = random.choice(ALFAMART_STORES)
    return toko

def pick_items_prioritize_tictac():
    items = []
    # 1-3 item Tic Tac
    tictac_count = random.randint(1, 3)
    for _ in range(tictac_count):
        nm, price = random.choice(PRODUCTS_TICTAC)
        qty = random.randint(1, 3)
        items.append((nm, qty, price))
    # Tambah 0-3 item lain
    others = random.randint(0, 3)
    for _ in range(others):
        nm, price = random.choice(PRODUCTS_OTHER)
        qty = random.randint(1, 2)
        items.append((nm, qty, price))
    return items

def generate_batch(n: int):
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_BASE / ts
    paths = []
    for i in range(1, n + 1):
        store = pick_random_store()
        items = pick_items_prioritize_tictac()
        diskon = random.choice([0, 1000, 2000, 3000, 0])
        voucher = random.choice([0, 0, 0, 2000])
        now_dt = dt.datetime.now()
        fn = f"struk_{i:03d}.png"
        out_path = out_dir / fn
        render_receipt_png(store, items, diskon, voucher, now_dt, out_path, LOGO_PATH)
        paths.append((fn, str(out_dir)))
    return ts, paths

# ================== ROUTES ==================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            n = int(request.form.get("jumlah", "1"))
            n = max(1, min(n, 200))
        except Exception:
            n = 1
        ts, paths = generate_batch(n)
        return redirect(url_for("result", ts=ts))
    return render_template("index.html")

@app.route("/result/<ts>")
def result(ts):
    folder = OUTPUT_BASE / ts
    if not folder.exists():
        return "Folder tidak ditemukan", 404
    files = sorted([f for f in folder.iterdir() if f.suffix.lower() == ".png"])
    return render_template("result.html", ts=ts, files=[f.name for f in files])

@app.route("/static/struk/<ts>/<filename>")
def serve_receipt(ts, filename):
    return send_from_directory(OUTPUT_BASE / ts, filename, as_attachment=False)

if __name__ == "__main__":
    # Jalankan lokal
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
