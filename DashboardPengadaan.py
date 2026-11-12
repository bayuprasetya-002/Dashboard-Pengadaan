import base64
import colorsys
import html
import inspect
import re
import sys
import textwrap
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st


try:
    import gspread
    import pandas as pd
    import plotly.express as px
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ModuleNotFoundError as import_error:
    st.error(
        "Library Python belum terpasang: {}. Jalankan perintah di bawah "
        "ini di terminal, lalu jalankan ulang aplikasi.".format(
            import_error.name
        )
    )
    st.code(
        '"{}" -m pip install gspread google-auth '
        "google-api-python-client pandas plotly".format(sys.executable),
        language="bash"
    )
    st.code(
        '"{}" -m streamlit run DashboardPengadaan.py'.format(sys.executable),
        language="bash"
    )
    st.stop()


# ==================================================
# KONFIGURASI DASHBOARD
# ==================================================

st.set_page_config(
    page_title="Dashboard Pengadaan",
    page_icon="📊",
    layout="wide"
)

DOCS = [
    "TOR",
    "Pakta Integritas User",
    "Formulir Pengajuan Pengadaan",
    "HPS",
    "Izin Prinsip",
    "Surat Permintaan Penawaran Proposal Vendor",
    "Proposal Vendor / Quotation",
    "Pakta Integritas Vendor",
    "Undangan Aanwijzing dan Negosiasi",
    "BA Aanwijzing dan BA Negosiasi Harga",
    "Surat Hasil Pengadaan/Usulan Pemenang",
    "SPK + Lampiran"
]

# Zona waktu WIB (UTC+7)
WIB = timezone(timedelta(hours=7))

# Lokasi logo. Folder dicari relatif terhadap file .py ini.
#   DashboardPengadaan.py
#   asset/
#       BRI.png
#       DWI.png
BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR_NAMES = ("asset", "assets")
LOGO_LEFT_FILE = "BRI.png"
LOGO_RIGHT_FILE = "DWI.png"
LOGO_LEFT_ALT = "Bank Rakyat Indonesia"
LOGO_RIGHT_ALT = "DWI - Digital Wholesale Banking & Innovation Management"

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}

# Status per dokumen (berdasarkan warna sel di spreadsheet)
#   Hijau  -> Done        (dihitung "Selesai")
#   Kuning -> On Progress (dihitung "Berjalan")
#   Putih  -> Pending     (dihitung "Belum Mulai")
# Palet warna Qlola Style (harus selaras dengan variabel :root di CSS)
BRAND_PRIMARY = "#0B63CE"     # Blue Qlola
BRAND_SECONDARY = "#00BFA5"   # Tosca
BRAND_ACCENT = "#0F2447"      # Navy
BRAND_ACCENT2 = "#FBFF00"     # Kuning
BRAND_SUCCESS = "#22C55E"     # Green
BRAND_INFO = "#3B82F6"        # Blue
BRAND_NEUTRAL = "#64748B"     # Gray
BRAND_TEXT = "#0F2447"        # Teks utama (navy)


PLOT_FONT_CSS = (
    '"Source Sans Pro", "Source Sans 3", "Source Sans", '
    '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
)
PLOT_FONT = PLOT_FONT_CSS

COLORS = {
    "Done": BRAND_SUCCESS,
    "On Progress": BRAND_ACCENT2,
    "Pending": "#C7D6EE",
}

PILL_CLASS = {
    "Done": "pill-done",
    "On Progress": "pill-progress",
    "Pending": "pill-pending",
}

# Nama tampilan status per dokumen
DOC_STATUS_LABEL = {
    "Done": "Selesai",
    "On Progress": "Berjalan",
    "Pending": "Belum Mulai",
}

# Status per pengadaan (gabungan 12 dokumen)
STATUS_ORDER = ["Selesai", "Berjalan", "Belum Mulai"]

# Nama kolom di spreadsheet. Spasi, baris baru, dan huruf besar diabaikan.
# Pencocokan: persis dulu, lalu "mengandung" (khusus kolom tanggal).
COLUMN_ALIASES = {
    "Nama Pengadaan": ["Nama Pengadaan"],
    "Tipe": ["Tipe"],
    "PIC": ["PIC"],
    "Vendor": ["Vendor"],
    "No": ["No", "No.", "Nomor", "No_Pengadaan", "Nomor Pengadaan"],
    "Tanggal TOR": [
        "Tanggal TOR Diterima",
        "Tanggal TOR",
        "TOR Diterima",
    ],
    "Tanggal Request": [
        "Tanggal Request Pengadaan",
        "Tanggal Request",
        "Request Pengadaan",
    ],
    "Tanggal Selesai": [
        "Pengadaan Selesai",
        "Tanggal Pengadaan Selesai",
        "Tanggal Selesai Pengadaan",
        "Tanggal Selesai",
    ],
}

# Kolom yang boleh dicocokkan dengan cara "mengandung"
FUZZY_COLUMNS = {"Tanggal TOR", "Tanggal Request", "Tanggal Selesai"}

# Kolom tujuan penulisan waiting time di spreadsheet (cocok persis,
# spasi/huruf besar diabaikan)
WAITING_ALIASES = {
    "Waiting TOR": [
        "Waiting Time TOR",
        "Waiting TOR",
    ],
    "Waiting Pengadaan": [
        "Waiting Time Pengadaan",
        "Waiting Pengadaan",
    ],
}



MENU_SUMMARY = "📋 Ringkasan"
MENU_DETAIL = "🔍 Detail Pengadaan"
MENU_PAYMENT = "💳 Pembayaran Pengadaan"
MENU_PAY_DETAIL = "🧾 Detail Pembayaran"

MENU_ITEMS = [MENU_SUMMARY, MENU_DETAIL, MENU_PAYMENT, MENU_PAY_DETAIL]
PAYMENT_MENUS = (MENU_PAYMENT, MENU_PAY_DETAIL)
MENU_KEY = "menu_nav"


# ==================================================
# KONFIGURASI PEMBAYARAN PENGADAAN
# ==================================================

# Nama bulan (bahasa Indonesia) urutan 1-12 dan singkatannya.
MONTH_NAMES = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]
MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
]

# Nama bulan di header sheet -> nomor bulan (huruf kecil, tanpa spasi).
# Singkatan 3 huruf ikut diterima (mis. "Agu", "Okt").
MONTH_LOOKUP = {}
for _index, _name in enumerate(MONTH_NAMES, start=1):
    MONTH_LOOKUP[_name.lower()] = _index
    MONTH_LOOKUP[_name[:3].lower()] = _index
MONTH_LOOKUP["sept"] = 9

# Worksheet pembayaran (spreadsheet yang sama dengan data pengadaan).
# Ubah lewat secrets: [google_sheet] payment_worksheet_name = "Sheet2"
PAY_SHEET_DEFAULT = "Sheet2"

# Hanya pengadaan dengan kolom Status = "Running" yang ditampilkan.
PAY_RUNNING_STATUS = "running"

# Nama tampilan status per cicilan (berdasarkan warna sel di spreadsheet)
#   Hijau  -> Done        (dibayar)
#   Kuning -> On Progress (sedang diproses)
#   Putih  -> Pending     (belum mulai)
PAY_STATUS_LABEL = {
    "Done": "Dibayar",
    "On Progress": "Diproses",
    "Pending": "Belum Mulai",
}

# Nama kolom informasi di sheet pembayaran (spasi/huruf besar diabaikan)
PAY_COLUMN_ALIASES = {
    "No": ["No", "No.", "Nomor"],
    "Jenis": ["Jenis"],
    "Nama": ["Project", "Nama Pengadaan", "Nama Project"],
    "SPK": ["Tanggal SPK"],
    "Nilai": ["Nilai Pengadaan"],
    "Status": ["Status"],
    "Durasi": ["Durasi (Bulan)", "Durasi"],
}


# ==================================================
# GAYA TAMPILAN (CSS)
#
# Selector sengaja dibuat ganda (lama + baru) dan memakai !important
# supaya tampilan tetap sama di berbagai versi Streamlit (lokal maupun
# Streamlit Community Cloud).
# ==================================================

st.markdown(
    """
<style>
/* ==================================================
   PALET WARNA — Qlola Style
   Ubah warna cukup di blok :root ini.
   ================================================== */
:root {
    /* Palet utama */
    --q-primary: #0B63CE;       /* Blue Qlola */
    --q-primary-dark: #0954B0;
    --q-secondary: #00BFA5;     /* Tosca */
    --q-accent: #FBFF00;        /* Kuning */
    --q-success: #22C55E;       /* Green */
    --q-info: #3B82F6;          /* Blue */
    --q-neutral: #64748B;       /* Gray */

    /* Turunan untuk teks, garis, dan latar */
    --q-navy: #0A2A66;
    --q-text: #0F2447;
    --q-text-soft: #334A6E;
    --q-muted: #64748B;
    --q-line: #DCE6F5;
    --q-line-soft: #EAF1FB;
    --q-tint: #F1F6FD;
    --q-pending: #C7D6EE;

    --q-glow: 0 8px 24px rgba(11, 99, 206, 0.10),
              0 1px 3px rgba(15, 36, 71, 0.06);

    /* Tinggi logo di header (BRI & DWI). Ubah bila ingin lebih
       besar / kecil. Nilai ini otomatis mengecil di layar sempit
       (lihat blok RESPONSIF di bagian bawah CSS). */
    --logo-height: 64px;

    /* Posisi tombol Refresh di sebelah kanan menu.
       Geser angka ini bila ingin menaikkan / menurunkan tombol. */
    --refresh-top: 1rem;

    /* Kunci ke tema terang walau browser/OS memakai mode gelap */
    color-scheme: light;
}

html,
body,
.stApp,
[data-testid="stAppViewContainer"] {
    color-scheme: light;
}

/* Cegah browser HP memperbesar teks sendiri saat layar diputar */
html {
    -webkit-text-size-adjust: 100%;
    text-size-adjust: 100%;
}

/* ---------- Latar belakang ---------- */
.stApp {
    color: var(--q-text);
    background:
        radial-gradient(900px 480px at 6% -4%, rgba(11, 99, 206, 0.12), transparent 62%),
        radial-gradient(760px 460px at 100% 8%, rgba(0, 191, 165, 0.10), transparent 60%),
        linear-gradient(180deg, #EDF4FE 0%, #F6F9FE 55%, #F3F7FD 100%);
    background-attachment: fixed;
}
[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    padding-top: 1.7rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

/* ---------- Header: logo kiri | judul tengah | logo kanan ---------- */
.app-header {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 16px 24px;
    margin-bottom: 4rem;
}
.hdr-left {
    justify-self: start;
}
.hdr-right {
    justify-self: end;
}
.hdr-center {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    text-align: center;
}
.app-logo {
    display: block;
    height: var(--logo-height);
    width: auto;
    max-width: 240px;
    object-fit: contain;
    /* Latar putih pada file PNG ikut menyatu dengan latar halaman */
    mix-blend-mode: multiply;
}

/* ---------- Judul halaman ---------- */
.app-title {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
}
.app-title-icon {
    flex: 0 0 auto;
    width: 46px;
    height: 46px;
    border-radius: 14px;
    background: #FFFFFF;
    color: var(--q-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: var(--q-glow);
}
.app-title-icon svg {
    stroke-width: 3;
}
.app-title-text {
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: -0.01em;
    color: var(--q-navy);
}
.app-subtitle {
    font-size: 0.85rem;
    color: var(--q-muted);
}

/* Layar sempit: logo di baris atas, judul di bawahnya */
@media (max-width: 900px) {
    :root {
        --logo-height: 48px;
    }
    .app-header {
        grid-template-columns: 1fr 1fr;
        grid-template-areas:
            "left right"
            "center center";
        margin-bottom: 2rem;
    }
    .hdr-left   { grid-area: left; }
    .hdr-right  { grid-area: right; }
    .hdr-center { grid-area: center; }
    .app-title-text {
        font-size: 1.4rem;
    }
    .app-title-icon {
        width: 38px;
        height: 38px;
    }
}

.stApp [data-testid="stCaptionContainer"] {
    color: var(--q-muted);
}

/* ---------- Pill status sinkronisasi ---------- */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    margin: 12px 0 10px 0;
    border-radius: 999px;
    background: rgba(34, 197, 94, 0.12);
    color: #15803D;
    font-size: 0.8rem;
    font-weight: 600;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--q-success);
}

/* ---------- Tombol ---------- */
.stApp .stButton > button {
    background: var(--q-primary) !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 700;
    box-shadow: 0 6px 16px rgba(11, 99, 206, 0.30);
}
.stApp .stButton > button,
.stApp .stButton > button p,
.stApp .stButton > button span {
    color: #FFFFFF !important;
}
.stApp .stButton > button:hover,
.stApp .stButton > button:focus,
.stApp .stButton > button:active {
    background: var(--q-primary-dark) !important;
    border: none !important;
    color: #FFFFFF !important;
}

/* ---------- Tombol Refresh (sejajar dengan menu, di kanan) ----------
   Wadah tombol dibuat selebar penuh dan setinggi 0, lalu tombolnya
   diposisikan absolut di sisi KANAN baris menu. Lebar penuh wajib agar
   "right: 0" menempel ke tepi kanan halaman (bukan ke tepi kiri).
   Ukuran disamakan dengan menu (tinggi 40px, padding 0 16px, pil).
   Di layar sempit tombol dipindah ke atas menu (lihat blok RESPONSIF). */
.stApp .st-key-refresh_btn {
    position: relative !important;
    width: 100% !important;
    max-width: 100% !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: visible !important;
    z-index: 20;
}
.stApp .st-key-refresh_btn > div,
.stApp .st-key-refresh_btn .stButton {
    position: static !important;
    width: 100% !important;
    overflow: visible !important;
}
.stApp .st-key-refresh_btn button {
    position: absolute !important;
    right: 0 !important;
    left: auto !important;
    top: var(--refresh-top) !important;
    width: auto !important;
    height: 40px !important;
    min-height: 40px !important;
    padding: 0 18px !important;
    white-space: nowrap;
}
.stApp .st-key-refresh_btn button p {
    font-size: 0.95rem;
    line-height: 1;
}

/* ---------- Tab (bentuk pil) ----------
   Memakai role="tab" / role="tablist" (stabil di semua versi) di samping
   selector baseweb. Garis bawah & highlight bawaan (merah) disembunyikan,
   tab aktif menjadi pil biru. */
.stApp [data-baseweb="tab-list"],
.stApp [role="tablist"] {
    gap: 8px !important;
    border-bottom: none !important;
    box-shadow: none !important;
    background: transparent !important;
}
.stApp [data-baseweb="tab-border"],
.stApp [data-baseweb="tab-highlight"] {
    display: none !important;
    height: 0 !important;
    background: transparent !important;
}
.stApp button[role="tab"],
.stApp [data-baseweb="tab"] {
    height: 40px !important;
    padding: 0 16px !important;
    border-radius: 999px !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.stApp button[role="tab"]:hover,
.stApp [data-baseweb="tab"]:hover {
    background: rgba(11, 99, 206, 0.08) !important;
}
.stApp button[role="tab"] p,
.stApp button[role="tab"] span,
.stApp button[role="tab"] div,
.stApp [data-baseweb="tab"] p {
    color: var(--q-neutral) !important;
    font-weight: 600;
}
.stApp button[role="tab"][aria-selected="true"],
.stApp [data-baseweb="tab"][aria-selected="true"],
.stApp button[role="tab"][aria-selected="true"]:hover,
.stApp [data-baseweb="tab"][aria-selected="true"]:hover {
    background: var(--q-primary) !important;
    box-shadow: 0 6px 16px rgba(11, 99, 206, 0.28) !important;
}
.stApp button[role="tab"][aria-selected="true"] p,
.stApp button[role="tab"][aria-selected="true"] span,
.stApp button[role="tab"][aria-selected="true"] div,
.stApp [data-baseweb="tab"][aria-selected="true"] p {
    color: #FFFFFF !important;
    font-weight: 700;
}

/* ---------- Menu utama (pil) ----------
   Menu memakai st.radio horizontal (key "menu_nav") agar filter dan
   kartu di atasnya bisa mengikuti menu yang aktif. Tampilannya dibuat
   sama dengan tab pil: lingkaran radio disembunyikan, pilihan aktif
   menjadi pil biru. */
.stApp .st-key-menu_nav [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    align-items: center;
    gap: 8px !important;
    background: transparent !important;
}
.stApp .st-key-menu_nav label[data-baseweb="radio"] {
    height: 40px;
    margin: 0 !important;
    padding: 0 16px !important;
    border-radius: 999px;
    background: transparent !important;
    display: flex !important;
    align-items: center;
    cursor: pointer;
    box-shadow: none;
}
/* Sembunyikan lingkaran radio (semua anak langsung selain teks) */
.stApp .st-key-menu_nav label[data-baseweb="radio"] > div:not(:has([data-testid="stMarkdownContainer"])),
.stApp .st-key-menu_nav label[data-baseweb="radio"] > span {
    display: none !important;
}
.stApp .st-key-menu_nav label[data-baseweb="radio"] > div {
    margin: 0 !important;
    padding: 0 !important;
}
.stApp .st-key-menu_nav label[data-baseweb="radio"]:hover {
    background: rgba(11, 99, 206, 0.08) !important;
}
.stApp .st-key-menu_nav label[data-baseweb="radio"] p,
.stApp .st-key-menu_nav label[data-baseweb="radio"] div {
    color: var(--q-neutral) !important;
    font-weight: 600;
    margin: 0;
}
.stApp .st-key-menu_nav label[data-baseweb="radio"]:has(input:checked),
.stApp .st-key-menu_nav label[data-baseweb="radio"]:has(input:checked):hover {
    background: var(--q-primary) !important;
    box-shadow: 0 6px 16px rgba(11, 99, 206, 0.28);
}
.stApp .st-key-menu_nav label[data-baseweb="radio"]:has(input:checked) p,
.stApp .st-key-menu_nav label[data-baseweb="radio"]:has(input:checked) div {
    color: #FFFFFF !important;
    font-weight: 700;
}

/* ---------- Filter (input, pilihan, tag) ---------- */
.stApp [data-testid="stWidgetLabel"] p {
    color: var(--q-text);
    font-weight: 600;
    font-size: 0.85rem;
}
.stApp [data-baseweb="input"],
.stApp [data-baseweb="select"] > div {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1px solid var(--q-line) !important;
    border-radius: 10px !important;
}
.stApp [data-baseweb="input"]:focus-within,
.stApp [data-baseweb="select"] > div:focus-within {
    border-color: var(--q-primary) !important;
}

/* Kolom "Cari pengadaan" & pilihan: latar putih (termasuk lapisan dalam) */
.stApp [data-baseweb="base-input"],
.stApp [data-baseweb="input"] input,
.stApp [data-baseweb="base-input"] input,
.stApp [data-testid="stTextInput"] input,
.stApp [data-baseweb="select"] input {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
}

.stApp span[data-baseweb="tag"] {
    background-color: rgba(11, 99, 206, 0.12) !important;
}
.stApp span[data-baseweb="tag"] span {
    color: var(--q-primary) !important;
    font-weight: 600;
}

/* ---------- Teks & ikon filter (terbaca di mode terang & gelap) ----------
   Di laptop dengan mode gelap, Streamlit memberi warna TERANG pada teks
   input dan daftar pilihan. Karena latar kolom dipaksa putih, warna teks
   juga harus dipaksa gelap agar tidak "putih di atas putih". */
.stApp input,
.stApp textarea,
.stApp [data-baseweb="input"] input,
.stApp [data-baseweb="select"] input,
.stApp [data-testid="stTextInput"] input {
    color: var(--q-text) !important;
    -webkit-text-fill-color: var(--q-text) !important;
    caret-color: var(--q-primary) !important;
}
.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #94A3B8 !important;
    -webkit-text-fill-color: #94A3B8 !important;
    opacity: 1 !important;
}
.stApp [data-baseweb="select"] div,
.stApp [data-baseweb="select"] span {
    color: var(--q-text) !important;
}
.stApp [data-baseweb="select"] svg {
    fill: var(--q-text-soft) !important;
    color: var(--q-text-soft) !important;
}

/* ---------- Daftar pilihan (dropdown) ----------
   Dropdown dirender di luar .stApp (langsung di <body>), jadi selector
   TIDAK boleh diawali .stApp. Dibuat putih dengan teks gelap. */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] ul,
ul[role="listbox"] {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: var(--q-text) !important;
}
[data-baseweb="popover"] > div {
    border: 1px solid var(--q-line) !important;
    border-radius: 10px !important;
    box-shadow: 0 10px 28px rgba(15, 36, 71, 0.14) !important;
}
[data-baseweb="popover"] div,
[data-baseweb="popover"] span,
[data-baseweb="popover"] li,
[data-baseweb="popover"] li *,
ul[role="listbox"] li,
li[role="option"],
li[role="option"] * {
    color: var(--q-text) !important;
}
[data-baseweb="popover"] li,
li[role="option"] {
    background-color: transparent !important;
}
[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] li[aria-selected="true"],
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {
    background-color: var(--q-tint) !important;
}

/* ---------- Kotak peringatan / info ----------
   Di laptop dengan mode gelap, teks kotak st.info / st.warning / st.error
   berwarna TERANG di atas latar yang terang, sehingga tidak terbaca.
   Teksnya dipaksa gelap (ikon tidak diubah). */
.stApp [data-testid="stAlert"] {
    border-radius: 12px;
}
.stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
.stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"] *,
.stApp [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"],
.stApp [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] * {
    color: var(--q-text) !important;
}

/* ---------- Grafik dalam kartu putih ----------
   Padding kartu dibuat 0 (jarak diatur lewat margin grafik di Plotly)
   supaya legenda di bagian bawah tidak terpotong. */
.stApp [data-testid="stPlotlyChart"] {
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-radius: 16px;
    padding: 0 !important;
    overflow: hidden;
    box-shadow: var(--q-glow);
}

/* Font tulisan grafik dipaksa sama di semua laptop (bukan monospace),
   dan warnanya navy agar mudah dibaca. */
.stApp [data-testid="stPlotlyChart"] svg text,
.stApp [data-testid="stPlotlyChart"] .main-svg text {
    font-family: "Source Sans Pro", "Source Sans 3", "Source Sans",
                 "Segoe UI", Roboto, "Helvetica Neue", Arial,
                 sans-serif !important;
}

/* ---------- Ikon dalam kotak kecil ---------- */
.ico {
    display: block;
}
.chip {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 8px;
    color: var(--accent, var(--q-primary));
    background: rgba(11, 99, 206, 0.10);
    background: color-mix(in srgb, var(--accent, #0B63CE) 14%, #FFFFFF);
}
.chip-lg {
    width: 40px;
    height: 40px;
    border-radius: 12px;
}

/* ---------- Kartu KPI ---------- */
.kpi {
    position: relative;
    overflow: hidden;
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-radius: 16px;
    padding: 16px 18px;
    height: 100%;
    box-shadow: var(--q-glow);
}
.kpi::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 64px;
    height: 3px;
    border-radius: 0 0 4px 0;
    background: var(--accent, var(--q-primary));
}
.kpi .label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--q-text-soft);
}
.kpi .value {
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1.2;
    color: var(--q-navy);
    margin-top: 8px;
    overflow-wrap: anywhere;
}
.kpi .sub {
    font-size: 0.78rem;
    color: var(--q-muted);
    margin-top: 4px;
}

/* Kartu KPI lebar dengan ikon bulat (waiting time) */
.kpi-wide {
    display: flex;
    align-items: center;
    gap: 16px;
}
.kpi-wide .kw-body {
    min-width: 0;
}
.kpi-wide .value {
    font-size: 1.7rem;
    margin-top: 4px;
}
.big-icon {
    flex: 0 0 auto;
    width: 54px;
    height: 54px;
    border-radius: 50%;
    background: #FFFFFF;
    color: var(--accent, var(--q-primary));
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 6px 18px rgba(11, 99, 206, 0.15),
                inset 0 0 0 1px var(--q-line-soft);
}

/* ---------- Kartu info kecil ---------- */
.info-card {
    display: flex;
    align-items: center;
    gap: 12px;
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-radius: 14px;
    padding: 12px 16px;
    height: 100%;
    box-shadow: var(--q-glow);
}
.info-card .label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--q-muted);
}
.info-card .value {
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--q-navy);
    margin-top: 2px;
}

/* ---------- Progress bar (detail) ---------- */
.pbar-head {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--q-navy);
}
.pbar {
    background: var(--q-line);
    border-radius: 999px;
    height: 12px;
    overflow: hidden;
    margin: 6px 0 2px 0;
}
.pbar > div {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--q-success), var(--q-secondary));
}

/* ---------- Pill status ---------- */
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
}
.pill-done     { background: rgba(34, 197, 94, 0.14);  color: #15803D; }
.pill-progress { background: rgba(245, 158, 11, 0.16); color: #B45309; }
.pill-pending  { background: rgba(100, 116, 139, 0.14); color: #475569; }

/* ---------- Kartu dokumen ---------- */
.doc-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(250px, 100%), 1fr));
    gap: 12px;
}
.doc-card {
    display: flex;
    align-items: center;
    gap: 12px;
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-radius: 14px;
    padding: 12px 14px;
    box-shadow: var(--q-glow);
}
.doc-no {
    flex: 0 0 auto;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-weight: 700;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(100, 116, 139, 0.14);
    color: #475569;
}
.doc-card.done .doc-no     { background: rgba(34, 197, 94, 0.14);  color: #15803D; }
.doc-card.progress .doc-no { background: rgba(245, 158, 11, 0.16); color: #B45309; }
.doc-name {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--q-text);
    line-height: 1.3;
    margin-bottom: 4px;
}

/* ---------- Judul bagian ---------- */
.section-title {
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--q-navy);
    margin: 1.2rem 0 0.6rem 0;
}

/* ---------- Tabel Daftar Pengadaan ---------- */
.tbl-wrap {
    overflow: auto;
    max-height: 640px;
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-radius: 16px;
    box-shadow: var(--q-glow);
}

/* Scrollbar tabel: selalu terlihat (tidak disembunyikan sistem operasi
   seperti pada scrollbar "overlay" di Windows/macOS tertentu).
   Chrome, Edge, Safari memakai ::-webkit-scrollbar; Firefox memakai
   scrollbar-color (dibungkus @supports agar tidak saling menimpa). */
.tbl-wrap::-webkit-scrollbar {
    width: 12px;
    height: 12px;
}
.tbl-wrap::-webkit-scrollbar-track {
    background: var(--q-tint);
}
.tbl-wrap::-webkit-scrollbar-thumb {
    background: #8A94A6;
    border-radius: 999px;
    border: 3px solid var(--q-tint);
}
.tbl-wrap::-webkit-scrollbar-thumb:hover {
    background: #64748B;
}
.tbl-wrap::-webkit-scrollbar-corner {
    background: var(--q-tint);
}
@supports (-moz-appearance: none) {
    .tbl-wrap {
        scrollbar-width: auto;
        scrollbar-color: #8A94A6 var(--q-tint);
    }
}

.proc-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.86rem;
    color: var(--q-text);
}
.proc-table th {
    position: sticky;
    z-index: 2;
    box-sizing: border-box;
    background: #0B63CE;
    color: #FFFFFF;
    font-weight: 700;
    text-align: center;
    padding: 0 10px;
    white-space: nowrap;
    border-right: 1px solid rgba(255, 255, 255, 0.14);
    border-bottom: 1px solid rgba(255, 255, 255, 0.14);
}
.proc-table thead tr.h1 th { top: 0; height: 38px; }
.proc-table thead tr.h2 th { top: 38px; height: 32px; padding: 0 4px; }
.proc-table th.th-left { text-align: left; }
.proc-table th:last-child { border-right: none; }
.proc-table td {
    padding: 9px 10px;
    border-bottom: 1px solid var(--q-line-soft);
    border-right: 1px solid var(--q-line-soft);
    vertical-align: middle;
    background: #FFFFFF;
}
.proc-table tbody tr:hover td { background: var(--q-tint); }
.proc-table tbody tr:last-child td { border-bottom: none; }
.proc-table td.c-no {
    text-align: center;
    color: var(--q-muted);
    font-weight: 600;
    width: 44px;
}
.proc-table td.c-name {
    min-width: 300px;
    line-height: 1.35;
    font-weight: 600;
}
.proc-table td.c-tipe,
.proc-table td.c-pic {
    white-space: nowrap;
    color: var(--q-text-soft);
}
.proc-table td.dc {
    width: 42px;
    min-width: 42px;
    text-align: center;
    padding: 6px 2px;
}
.proc-table td.c-prog {
    min-width: 150px;
    border-right: none;
}

/* ---------- Ikon status dokumen ---------- */
.chk {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--q-success);
    color: #FFFFFF;
    font-size: 0.8rem;
    font-weight: 800;
    line-height: 1;
}
.dot {
    display: inline-block;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--q-accent);
    vertical-align: middle;
}
.empty-box {
    display: inline-block;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #FFFFFF;
    border: 2px solid var(--q-pending);
    vertical-align: middle;
}

/* ---------- Progres di tabel ---------- */
.pg-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
}
.pg-bar {
    flex: 1 1 auto;
    height: 8px;
    background: var(--q-line);
    border-radius: 999px;
    overflow: hidden;
}
.pg-bar > div {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--q-primary), var(--q-info));
}
.pg-text {
    flex: 0 0 auto;
    min-width: 46px;
    text-align: right;
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--q-navy);
}

/* ---------- Keterangan kelengkapan dokumen ---------- */
.legend-box {
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-radius: 16px;
    padding: 18px 22px;
    margin-top: 14px;
    box-shadow: var(--q-glow);
}
.legend-title {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--q-navy);
    margin-bottom: 14px;
}
.legend-title::after {
    content: "";
    display: block;
    width: 36px;
    height: 3px;
    margin-top: 6px;
    border-radius: 3px;
    background: var(--q-primary);
}
.legend-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
    gap: 10px 20px;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--q-text);
    line-height: 1.35;
}
.legend-no {
    flex: 0 0 auto;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--q-primary);
    color: #FFFFFF;
    font-size: 0.75rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
}
.legend-status {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 28px;
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid var(--q-line-soft);
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--q-text-soft);
}
.legend-status > span {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

/* ---------- Pembayaran Pengadaan ---------- */
.proc-table thead tr.h3 th { top: 70px; height: 32px; padding: 0 4px; }
.proc-table td.c-start {
    white-space: nowrap;
    text-align: center;
    color: var(--q-text-soft);
    font-weight: 600;
}
.doc-meta {
    font-size: 0.8rem;
    color: var(--q-text-soft);
    line-height: 1.4;
    margin-bottom: 4px;
}
.legend-status.solo {
    margin-top: 0;
    padding-top: 0;
    border-top: none;
}

/* ---------- Tabel Pembayaran: kolom tetap, bulan bisa digeser ----------
   Hanya kolom tahun/bulan yang bergeser saat di-scroll horizontal.
   Kolom No, Nama Pengadaan, dan Mulai Pembayaran dikunci di KIRI
   (sticky left), kolom Progres dikunci di KANAN (sticky right).
   Lebar kolom tetap dibuat eksplisit supaya posisi "left" tiap kolom
   tetap akurat. Bila lebar kolom diubah, ubah juga nilai left kolom
   sesudahnya (s2 = lebar s1, s3 = lebar s1 + s2). */
.pay-table {
    width: max-content;
    min-width: 100%;
}
.pay-table .s1,
.pay-table .s2,
.pay-table .s3,
.pay-table .s4 {
    position: sticky;
    box-sizing: border-box;
}
.pay-table .s1 {
    left: 0;
    width: 44px;
    min-width: 44px;
    max-width: 44px;
}
.pay-table .s2 {
    left: 44px;
    width: 300px;
    min-width: 300px;
    max-width: 300px;
}
.pay-table .s3 {
    left: 344px;
    width: 150px;
    min-width: 150px;
    max-width: 150px;
}
.pay-table .s4 {
    right: 0;
    width: 170px;
    min-width: 170px;
    max-width: 170px;
}
/* Sel isi: di atas sel bulan saat digeser horizontal */
.pay-table td.s1,
.pay-table td.s2,
.pay-table td.s3,
.pay-table td.s4 {
    z-index: 3;
}
/* Sel header kolom tetap: di atas semua header lain */
.pay-table th.s1,
.pay-table th.s2,
.pay-table th.s3,
.pay-table th.s4 {
    z-index: 6;
}
/* Garis bayangan pemisah antara kolom tetap dan kolom yang bergeser */
.pay-table .s3 {
    box-shadow: 6px 0 8px -6px rgba(15, 36, 71, 0.28);
}
.pay-table .s4 {
    box-shadow: -6px 0 8px -6px rgba(15, 36, 71, 0.28);
}
.pay-table td.s4 {
    border-right: none;
}
/* Kolom bulan: lebar tetap agar tabel melebar & bisa digeser */
.pay-table td.dc,
.pay-table thead tr.h3 th {
    min-width: 48px;
}

/* Layar sempit: kolom tetap dipersempit */
@media (max-width: 900px) {
    .pay-table .s2 {
        width: 170px;
        min-width: 170px;
        max-width: 170px;
    }
    .pay-table .s3 {
        left: 214px;
        width: 110px;
        min-width: 110px;
        max-width: 110px;
    }
    .pay-table .s4 {
        width: 130px;
        min-width: 130px;
        max-width: 130px;
    }
    .pay-table td.c-name {
        min-width: 0;
    }
}

/* ---------- Detail Pembayaran: jadwal per bulan ----------
   Jumlah kolom (--cols) diatur dari Python mengikuti jumlah cicilan:
   4 cicilan -> 4 kolom (1 baris), 6 cicilan -> 3 kolom (2 baris), dst.
   Semua kartu sama tinggi dan isinya seragam. */
.pay-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0 0 14px 0;
}
.pay-grid {
    display: grid;
    grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr));
    gap: 14px;
}
@media (max-width: 900px) {
    .pay-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
@media (max-width: 560px) {
    .pay-grid {
        grid-template-columns: 1fr;
    }
}
.pay-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
    background: #FFFFFF;
    border: 1px solid var(--q-line-soft);
    border-top: 4px solid var(--pay-accent, var(--q-pending));
    border-radius: 16px;
    padding: 14px 16px 16px 16px;
    box-shadow: var(--q-glow);
}
.pay-card.done     { --pay-accent: var(--q-success); }
.pay-card.progress { --pay-accent: var(--q-accent); }
.pay-head {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}
.pay-no {
    flex: 0 0 auto;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    font-weight: 700;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(100, 116, 139, 0.14);
    color: #475569;
}
.pay-card.done .pay-no     { background: rgba(34, 197, 94, 0.14);  color: #15803D; }
.pay-card.progress .pay-no { background: rgba(245, 158, 11, 0.16); color: #B45309; }
.pay-month {
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--q-navy);
    line-height: 1.25;
}
.pay-amount {
    font-size: 1.3rem;
    font-weight: 800;
    line-height: 1.2;
    color: var(--q-navy);
    overflow-wrap: anywhere;
}
.pay-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.pay-meta-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--q-muted);
}
.pay-meta-value {
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--q-text-soft);
}
.pay-foot {
    margin-top: auto;
}

/* ==================================================
   RESPONSIF — laptop (berbagai resolusi / zoom), tablet, dan HP
   Blok ini sengaja diletakkan PALING AKHIR agar menimpa aturan di
   atasnya. Breakpoint:
     >= 1800px : layar lebar
     <= 1280px : laptop kecil
     <= 1100px : tombol Refresh pindah ke atas menu
     <=  900px : tablet (kartu & filter 2 per baris)
     <=  640px : HP (1 kolom, tabel lebih padat)
     <=  480px : HP kecil
   ================================================== */

/* ---------- Ukuran teks fleksibel (mengikuti lebar layar) ---------- */
.app-title-text {
    font-size: clamp(1.25rem, 1rem + 1.2vw, 1.9rem);
}
.kpi .value {
    font-size: clamp(1.35rem, 1.05rem + 0.9vw, 1.9rem);
}
.kpi-wide .value {
    font-size: clamp(1.25rem, 1rem + 0.8vw, 1.7rem);
}
.pay-amount {
    font-size: clamp(1.1rem, 1rem + 0.5vw, 1.3rem);
}

/* Isi kartu boleh menyusut & membungkus (tidak mendorong kartu melebar) */
.info-card > div:last-child,
.doc-card > div:last-child {
    min-width: 0;
}
.info-card .value {
    overflow-wrap: anywhere;
}
.kpi .label span {
    min-width: 0;
}

/* Tabel: tinggi mengikuti tinggi layar, geser sentuh terasa halus */
.tbl-wrap {
    max-height: min(640px, 80vh);
    -webkit-overflow-scrolling: touch;
}

/* ---------- Layar lebar ---------- */
@media (min-width: 1800px) {
    .block-container {
        max-width: 1600px;
    }
}

/* ---------- Laptop kecil ---------- */
@media (max-width: 1280px) {
    :root {
        --logo-height: 56px;
    }
    .block-container {
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    .app-header {
        margin-bottom: 3rem;
    }
}

/* ---------- Tombol Refresh pindah ke atas menu ----------
   Bila layar tidak cukup lebar untuk menu + tombol dalam satu baris,
   tombol tidak lagi melayang di kanan menu (supaya tidak menimpa menu)
   melainkan tampil di atas menu. */
@media (max-width: 1100px) {
    .stApp .st-key-refresh_btn {
        height: auto !important;
        min-height: 0 !important;
        margin-bottom: 0.6rem;
    }
    .stApp .st-key-refresh_btn button {
        position: static !important;
        width: 100% !important;
    }
}

/* ---------- Tablet ---------- */
@media (max-width: 900px) {
    /* Kolom Streamlit (kartu KPI, filter, dsb.) membungkus 2 per baris */
    .stApp [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: 1rem !important;
    }
    .stApp [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    .stApp [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 calc(50% - 1rem) !important;
        min-width: calc(50% - 1rem) !important;
        width: auto !important;
    }
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }
}

/* ---------- HP ---------- */
@media (max-width: 640px) {
    :root {
        --logo-height: 44px;
    }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }

    /* Semua kolom Streamlit menjadi 1 per baris */
    .stApp [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    .stApp [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    .app-header {
        gap: 12px;
        margin-bottom: 1.5rem;
    }
    .app-logo {
        max-width: 150px;
    }
    .app-subtitle {
        font-size: 0.75rem;
        line-height: 1.4;
    }

    /* Menu pil lebih ringkas */
    .stApp .st-key-menu_nav [role="radiogroup"] {
        gap: 6px !important;
    }
    .stApp .st-key-menu_nav label[data-baseweb="radio"] {
        height: 36px;
        padding: 0 12px !important;
    }
    .stApp .st-key-menu_nav label[data-baseweb="radio"] p,
    .stApp .st-key-menu_nav label[data-baseweb="radio"] div {
        font-size: 0.82rem;
    }

    /* Kartu lebih padat */
    .kpi {
        padding: 12px 14px;
    }
    .kpi .label {
        font-size: 0.68rem;
    }
    .kpi-wide {
        gap: 12px;
    }
    .big-icon {
        width: 44px;
        height: 44px;
    }
    .info-card {
        padding: 10px 12px;
    }
    .doc-card {
        padding: 10px 12px;
    }
    .legend-box {
        padding: 14px 14px;
    }
    .section-title {
        font-size: 1.05rem;
    }

    /* Tabel lebih padat; geser horizontal tetap dipakai */
    .tbl-wrap {
        max-height: 75vh;
        border-radius: 12px;
    }
    .proc-table {
        font-size: 0.78rem;
    }
    .proc-table td {
        padding: 7px 8px;
    }
    .proc-table td.c-name {
        min-width: 210px;
    }
    .proc-table td.c-prog {
        min-width: 120px;
    }
    .proc-table th {
        padding: 0 8px;
    }

    /* Tabel Pembayaran: hanya kolom No dan Nama yang dikunci di kiri.
       Kolom Mulai Pembayaran dan Progres ikut bergeser, supaya kolom
       bulan masih punya ruang di layar sempit. */
    .pay-table .s2 {
        width: 130px;
        min-width: 130px;
        max-width: 130px;
        box-shadow: 6px 0 8px -6px rgba(15, 36, 71, 0.28);
    }
    .pay-table .s3,
    .pay-table .s4 {
        left: auto;
        right: auto;
        width: 120px;
        min-width: 120px;
        max-width: 120px;
        box-shadow: none;
    }
    .pay-table td.dc,
    .pay-table thead tr.h3 th {
        min-width: 44px;
    }

    /* Grafik batang: boleh digeser horizontal agar label tidak sesak.
       Wadahnya diberi key "chart_docs" lewat Python. */
    .stApp .st-key-chart_docs [data-testid="stPlotlyChart"] {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }
    .stApp .st-key-chart_docs [data-testid="stPlotlyChart"] > div {
        min-width: 560px;
    }
}

/* ---------- HP kecil ---------- */
@media (max-width: 480px) {
    :root {
        --logo-height: 38px;
    }
    .app-logo {
        max-width: 130px;
    }
    .app-title-text {
        font-size: 1.15rem;
    }
    .pay-card {
        padding: 12px 14px 14px 14px;
    }
}
</style>
""",
    unsafe_allow_html=True
)


# ==================================================
# UTILITAS UMUM
# ==================================================

def today_wib():
    return datetime.now(WIB).date()


def norm(text):
    """Huruf kecil dan tanpa spasi/newline apa pun."""
    return "".join(str(text).split()).lower()


def esc(value):
    """Escape HTML. Tanda $ juga diamankan agar tidak dibaca sebagai LaTeX."""
    return html.escape(str(value)).replace("$", "&#36;")


def show_chart(fig):
    """
    Tampilkan grafik Plotly selebar kolom. Versi Streamlit baru memakai
    width="stretch", versi lama memakai use_container_width=True.
    """
    try:
        params = inspect.signature(st.plotly_chart).parameters
    except (TypeError, ValueError):
        params = {}

    kwargs = {}

    if "width" in params:
        kwargs["width"] = "stretch"
    else:
        kwargs["use_container_width"] = True

    # theme=None: grafik tidak ikut mode gelap/terang Streamlit, sehingga
    # tampilannya sama di semua laptop.
    if "theme" in params:
        kwargs["theme"] = None

    # Toolbar Plotly disembunyikan: di layar sentuh toolbar ini menutupi
    # grafik dan mengganggu geseran halaman.
    if "config" in params:
        kwargs["config"] = {"displayModeBar": False}

    st.plotly_chart(fig, **kwargs)


def keyed_container(key):
    """
    Wadah dengan key (jadi class CSS "st-key-<key>"). Bila versi Streamlit
    belum mendukung parameter key, dipakai wadah biasa (tampilan tetap
    jalan, hanya tanpa geser horizontal grafik di HP).
    """
    try:
        return st.container(key=key)
    except TypeError:
        return st.container()


def get_setting(key, default):
    """Baca pengaturan opsional dari secrets bagian [google_sheet]."""
    try:
        return st.secrets["google_sheet"].get(key, default)
    except Exception:
        return default


def get_date_order():
    """
    Urutan tanggal bila ambigu (mis. 9/10/2026).
    Default "mdy" = bulan/hari/tahun (sesuai spreadsheet ini).
    Ubah lewat secrets: [google_sheet] date_order = "dmy"
    """
    value = get_setting("date_order", "mdy")
    return "dmy" if str(value).strip().lower() == "dmy" else "mdy"


def get_write_enabled():
    """
    Tulis waiting time ke spreadsheet? Default: ya.
    Matikan lewat secrets: [google_sheet] write_waiting_time = false
    """
    value = get_setting("write_waiting_time", True)
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def get_write_format():
    """
    Format isi sel waiting time di spreadsheet.
      "text"   (default) -> "93 hari"
      "number"           -> 93  (angka murni, bisa dijumlah/dirata-rata)
    Ubah lewat secrets: [google_sheet] waiting_write_format = "number"
    """
    value = get_setting("waiting_write_format", "text")
    return "number" if str(value).strip().lower() == "number" else "text"


def parse_date(text, date_order="mdy"):
    """
    Baca tanggal dari teks sel. Spreadsheet ini memakai format
    bulan/hari/tahun (contoh 9/29/2026). Format lain juga dicoba.
    """
    if text is None:
        return None

    if isinstance(text, datetime):
        return text.date()

    if isinstance(text, date):
        return text

    # Nomor seri tanggal Google Sheets (mis. 46294)
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        if 30000 < float(text) < 80000:
            return (datetime(1899, 12, 30) + timedelta(days=float(text))).date()
        return None

    text = str(text).strip()

    if not text or text.lower() in {"nan", "none", "nat", "-"}:
        return None

    candidates = [text]
    if " " in text:
        candidates.append(text.split()[0])

    if date_order == "dmy":
        slash_formats = ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%m/%d/%y")
    else:
        slash_formats = ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y")

    formats = (
        ("%Y-%m-%d",)
        + slash_formats
        + ("%d-%m-%Y", "%d %b %Y", "%d %B %Y")
    )

    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue

    return None


def as_date(value):
    """Nilai sel tanggal -> date, atau None bila kosong/tidak valid."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def fmt_date(value):
    if value is None:
        return "-"
    try:
        if pd.isna(value):
            return "-"
    except (TypeError, ValueError):
        pass
    return value.strftime("%d %b %Y")


def make_unique(headers):
    """Header kosong/duplikat dibuat unik agar DataFrame aman."""
    result = []
    seen = {}

    for index, name in enumerate(headers):
        name = str(name).strip()

        if not name:
            name = "_kolom{}".format(index)

        if name in seen:
            seen[name] += 1
            name = "{}_{}".format(name, seen[name])
        else:
            seen[name] = 0

        result.append(name)

    return result


def find_col(columns, names, fuzzy=False):
    """
    Cari nama kolom yang cocok (abaikan spasi/huruf besar).
    Tahap 1: cocok persis. Tahap 2 (fuzzy): header mengandung alias.
    Kolom 'Waiting Time ...' tidak pernah dipakai sebagai sumber tanggal.
    """
    wanted = [norm(n) for n in names]

    for col in columns:
        if norm(col) in wanted:
            return col

    if fuzzy:
        for alias in wanted:
            for col in columns:
                key = norm(col)
                if "waiting" in key:
                    continue
                if alias in key:
                    return col

    return None


def is_ket_row(row):
    """Baris keterangan ('Ket:') di bawah tabel."""
    for cell in list(row)[:3]:
        if norm(cell) in {"ket", "ket:", "keterangan", "keterangan:"}:
            return True
    return False


def col_letter(index):
    """Indeks kolom (mulai 0) -> huruf kolom Sheets: 0=A, 9=J, 26=AA."""
    index += 1
    letters = ""

    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters

    return letters


def waiting_days(start, end, today):
    """
    Jumlah hari waiting time.
      - tanggal selesai terisi  : selesai - mulai (nilai final)
      - tanggal selesai kosong  : hari ini - mulai (terus bertambah)
    Return None bila tanggal mulai kosong atau selesai < mulai.
    """
    if start is None:
        return None

    if end is not None:
        if end < start:
            return None
        return (end - start).days

    return max((today - start).days, 0)


def waiting_info(start, end, today):
    """
    Waiting time = tanggal selesai (jika sudah diisi) dikurangi tanggal mulai.
    Jika tanggal selesai belum diisi, dihitung sampai hari ini.
    Contoh: mulai tgl 15, selesai tgl 20 -> 5 hari; bila selesai diubah
    menjadi tgl 30 -> otomatis menjadi 15 hari.

    Return: (teks nilai, teks keterangan)
    """
    if start is None:
        return "-", "Tanggal mulai belum diisi"

    if end is not None:
        if end < start:
            return "-", "Tanggal selesai lebih awal dari tanggal mulai"

        days = (end - start).days
        return (
            "{} hari".format(days),
            "{} s/d {} (final)".format(fmt_date(start), fmt_date(end))
        )

    days = max((today - start).days, 0)
    return (
        "{} hari".format(days),
        "{} s/d hari ini (masih berjalan)".format(fmt_date(start))
    )


def waiting_cell(days, write_format):
    """
    Isi sel waiting time di spreadsheet.
    Return (teks pembanding, nilai yang ditulis).
    """
    if write_format == "number":
        if days is None:
            return "", ""
        return str(days), days

    if days is None:
        return "-", "-"

    text = "{} hari".format(days)
    return text, text


@st.cache_data
def image_data_uri(filename):
    """
    Baca gambar dari folder asset (atau assets) di samping file .py ini,
    lalu ubah menjadi data URI (base64) agar bisa disisipkan ke HTML.
    Return string kosong bila file tidak ditemukan.
    """
    for folder in ASSET_DIR_NAMES:
        path = BASE_DIR / folder / filename

        if path.is_file():
            mime = MIME_TYPES.get(path.suffix.lower(), "image/png")
            encoded = base64.b64encode(path.read_bytes()).decode()
            return "data:{};base64,{}".format(mime, encoded)

    return ""


# ==================================================
# KONEKSI GOOGLE SHEETS
# ==================================================

def get_credentials():

    account_info = dict(st.secrets["gcp_service_account"])

    if "private_key" in account_info:
        account_info["private_key"] = (
            account_info["private_key"].replace("\\n", "\n")
        )

    # Akses baca + tulis (dibutuhkan untuk mencatat waiting time).
    return Credentials.from_service_account_info(
        account_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets"
        ]
    )


@st.cache_resource
def connect_google():
    return gspread.authorize(get_credentials())


def with_retry(func, retries=3, delay=2):
    """
    Ulangi func() bila ada gangguan jaringan sesaat. Error konfigurasi
    (403/404, sheet tidak ditemukan, dsb.) langsung dilempar.
    """
    last_error = None

    for attempt in range(retries):
        try:
            return func()

        except (gspread.exceptions.GSpreadException, HttpError):
            raise

        except Exception as error:
            last_error = error
            time.sleep(delay * (attempt + 1))

    raise last_error


def write_updates(spreadsheet_id, updates):
    """Tulis banyak sel sekaligus (satu panggilan API)."""

    def do_write():
        service = build(
            "sheets",
            "v4",
            credentials=get_credentials(),
            cache_discovery=False
        )

        return service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": updates
            }
        ).execute(num_retries=3)

    return with_retry(do_write)


# ==================================================
# MEMBACA WARNA CELL
# ==================================================

def _valid_color(color):
    return isinstance(color, dict) and len(color) > 0


def extract_color(cell):
    for fmt_key in ("effectiveFormat", "userEnteredFormat"):
        fmt = cell.get(fmt_key, {}) or {}

        color = fmt.get("backgroundColor")
        if _valid_color(color):
            return color

        color = (fmt.get("backgroundColorStyle", {}) or {}).get("rgbColor")
        if _valid_color(color):
            return color

    return None


def classify_rgb(r, g, b):
    """Hijau = Done, Kuning/oranye = On Progress, lainnya (putih) = Pending."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue = h * 360

    # Putih, abu-abu, atau hampir hitam
    if s < 0.05 or v < 0.25:
        return "Pending"

    # Kuning / emas / oranye muda
    if 30 <= hue <= 70:
        return "On Progress"

    # Hijau
    if 70 < hue <= 170:
        return "Done"

    return "Pending"


def get_status(cell):
    color = extract_color(cell)

    if color is None:
        return "Pending"

    # API menghilangkan channel bernilai 0, jadi default = 0.
    r = round(float(color.get("red", 0)) * 255)
    g = round(float(color.get("green", 0)) * 255)
    b = round(float(color.get("blue", 0)) * 255)

    return classify_rgb(r, g, b)


def procurement_status_from_counts(done, on_progress, total_docs):
    """
    Status satu pengadaan dari 12 dokumennya:
      Selesai     : SEMUA dokumen hijau
      Belum Mulai : tidak ada dokumen hijau maupun kuning (semua putih)
      Berjalan    : selain itu (sebagian sudah hijau/kuning)
    """
    if done == total_docs:
        return "Selesai"
    if done + on_progress == 0:
        return "Belum Mulai"
    return "Berjalan"


# ==================================================
# DETEKSI STRUKTUR SHEET
# ==================================================

def find_header_row(values):
    for i, row in enumerate(values[:15]):
        if any(norm(c) == "namapengadaan" for c in row):
            return i
    return 0


def find_number_row(values, start):
    """
    Cari baris berisi angka 1..12 (header kolom dokumen), di baris header
    yang sama atau 1-3 baris di bawahnya.
    Return (index_baris, {nomor: index_kolom}) atau (None, {}).
    """
    expected = {str(i) for i in range(1, len(DOCS) + 1)}

    for i in range(start, min(start + 4, len(values))):
        mapping = {}

        for col_index, cell in enumerate(values[i]):
            text = str(cell).strip()

            if text.endswith(".0"):
                text = text[:-2]

            if text in expected and text not in mapping:
                mapping[text] = col_index

        if len(mapping) == len(expected):
            return i, mapping

    return None, {}


def build_headers(values, first, last):
    """
    Gabungkan teks header dari baris `first` sampai `last` per kolom.
    Header sheet ini bertingkat (sel di-merge), jadi 'Nama Pengadaan'
    bisa berada di baris atas sedangkan 'Tanggal TOR Diterima' di baris
    bawahnya. Dengan digabung, semua nama kolom tetap terbaca.
    """
    block = values[first:last + 1]
    width = max((len(r) for r in block), default=0)

    headers = []

    for c in range(width):
        parts = []

        for row in block:
            text = " ".join(str(row[c]).split()) if c < len(row) else ""
            if text and text not in parts:
                parts.append(text)

        headers.append(" ".join(parts))

    return make_unique(headers)


# ==================================================
# SINKRON WAITING TIME KE SPREADSHEET
# ==================================================

def sync_waiting_times(
    df,
    headers,
    values,
    spreadsheet_id,
    range_name,
    today,
    write_format,
    has_tor,
    has_request
):
    """
    Tulis Waiting Time TOR & Waiting Time Pengadaan ke kolom bernama
    'Waiting Time TOR' / 'Waiting Time Pengadaan' di spreadsheet.

    - Hanya sel yang nilainya berbeda yang ditulis (hemat kuota API).
    - Nilai dihitung dengan aturan yang sama seperti tampilan dashboard.
    - Hanya baris pengadaan yang ditulis; baris lain tidak disentuh.
    """
    tor_col = find_col(headers, WAITING_ALIASES["Waiting TOR"])
    req_col = find_col(headers, WAITING_ALIASES["Waiting Pengadaan"])

    targets = []

    if tor_col is not None and has_tor:
        targets.append((headers.index(tor_col), "Tgl TOR"))

    if req_col is not None and has_request:
        targets.append((headers.index(req_col), "Tgl Request"))

    if not targets:
        return {
            "status": "missing",
            "written": 0,
            "message": (
                "Kolom 'Waiting Time TOR' / 'Waiting Time Pengadaan' "
                "atau kolom tanggalnya tidak ditemukan, jadi tidak ada "
                "yang ditulis ke spreadsheet."
            )
        }

    updates = []

    for _, item in df.iterrows():

        sheet_row = int(item["_sheet_row"])
        end = as_date(item["Tgl Selesai"])

        for col_index, date_key in targets:

            start = as_date(item[date_key])
            days = waiting_days(start, end, today)

            compare_text, write_value = waiting_cell(days, write_format)

            current = ""
            if sheet_row < len(values) and col_index < len(values[sheet_row]):
                current = str(values[sheet_row][col_index]).strip()

            if current == compare_text:
                continue

            updates.append({
                "range": "{}!{}{}".format(
                    range_name,
                    col_letter(col_index),
                    sheet_row + 1
                ),
                "values": [[write_value]]
            })

    if updates:
        write_updates(spreadsheet_id, updates)

    return {
        "status": "ok",
        "written": len(updates),
        "message": ""
    }


# ==================================================
# MEMBACA DATA GOOGLE SHEETS
# ==================================================

@st.cache_data(ttl=30)
def load_data():

    spreadsheet_id = st.secrets["google_sheet"]["spreadsheet_id"]

    sheet_name = st.secrets["google_sheet"].get(
        "worksheet_name",
        "Sheet1"
    )

    date_order = get_date_order()

    # ----------------------------------------------
    # BACA NILAI (gspread)
    # ----------------------------------------------

    def fetch_values():
        client = connect_google()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet.get_all_values()

    values = with_retry(fetch_values)

    if not values:
        return pd.DataFrame(), {}

    # ----------------------------------------------
    # DETEKSI BARIS HEADER & BARIS NOMOR DOKUMEN
    # ----------------------------------------------

    header_row = find_header_row(values)
    number_row, number_map = find_number_row(values, header_row)

    if number_row is not None:
        last_header_row = max(header_row, number_row)
        data_start = last_header_row + 1
        doc_columns = {
            doc: number_map.get(str(n))
            for n, doc in enumerate(DOCS, start=1)
        }
        headers = build_headers(values, header_row, last_header_row)
    else:
        # Fallback: 12 kolom tepat setelah kolom "Vendor"
        data_start = header_row + 1
        headers = build_headers(values, header_row, header_row)
        vendor_idx = next(
            (i for i, h in enumerate(headers) if norm(h) == "vendor"),
            None
        )
        if vendor_idx is None:
            doc_columns = {doc: None for doc in DOCS}
        else:
            doc_columns = {
                doc: vendor_idx + 1 + n
                for n, doc in enumerate(DOCS)
            }

    # ----------------------------------------------
    # BENTUK DATAFRAME (berhenti di baris "Ket:")
    # ----------------------------------------------

    rows = []
    sheet_rows = []

    for offset, row in enumerate(values[data_start:]):

        if is_ket_row(row):
            break

        row = list(row)

        if len(row) < len(headers):
            row += [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[:len(headers)]

        rows.append(row)
        sheet_rows.append(data_start + offset)

    df = pd.DataFrame(rows, columns=headers)
    df["_sheet_row"] = sheet_rows

    # ----------------------------------------------
    # AMBIL FORMAT WARNA (googleapiclient)
    # ----------------------------------------------

    if str(sheet_name).replace("_", "").isalnum():
        range_name = str(sheet_name)
    else:
        range_name = "'{}'".format(str(sheet_name).replace("'", "''"))

    def fetch_colors():
        service = build(
            "sheets",
            "v4",
            credentials=get_credentials(),
            cache_discovery=False
        )

        return service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=["{}!A1:AZ{}".format(range_name, len(values))],
            includeGridData=True,
            fields=(
                "sheets(properties(title),"
                "data(rowData(values("
                "effectiveFormat(backgroundColor),"
                "userEnteredFormat(backgroundColor)))))"
            )
        ).execute(num_retries=3)

    response = with_retry(fetch_colors)

    sheet_data = response["sheets"][0]

    grid = sheet_data.get("data", [{}])[0].get("rowData", [])

    # ----------------------------------------------
    # PROSES STATUS DOKUMEN (warna tiap sel dokumen 1-12)
    # ----------------------------------------------

    statuses = []

    for sheet_row in df["_sheet_row"]:

        cells = (
            grid[sheet_row].get("values", [])
            if sheet_row < len(grid)
            else []
        )

        row_status = {}

        for doc in DOCS:
            col_index = doc_columns.get(doc)

            if col_index is None or col_index >= len(cells):
                row_status[doc] = "Pending"
                continue

            row_status[doc] = get_status(cells[col_index])

        statuses.append(row_status)

    for doc in DOCS:
        df[doc] = [row[doc] for row in statuses]

    # ----------------------------------------------
    # SERAGAMKAN NAMA KOLOM INFORMASI
    # ----------------------------------------------

    source_cols = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        source_cols[canonical] = find_col(
            df.columns,
            aliases,
            fuzzy=canonical in FUZZY_COLUMNS
        )

    for canonical in ["Nama Pengadaan", "Tipe", "PIC", "Vendor"]:
        found = source_cols[canonical]

        if found is None:
            df[canonical] = "-"
        elif found != canonical:
            df[canonical] = df[found]

    df["Nama Pengadaan"] = (
        df["Nama Pengadaan"].fillna("").astype(str).str.strip()
    )

    # Hanya baris yang punya nama pengadaan
    # (pengadaan baru otomatis ikut)
    df = df[
        df["Nama Pengadaan"].ne("")
        & df["Nama Pengadaan"].str.lower().ne("nan")
        & df["Nama Pengadaan"].str.lower().ne("none")
    ].copy().reset_index(drop=True)

    for col in ["Tipe", "PIC", "Vendor"]:
        df[col] = (
            df[col].fillna("").astype(str).str.strip()
            .replace({"": "-", "nan": "-", "None": "-"})
        )

    df["Done"] = df[DOCS].eq("Done").sum(axis=1).astype(int)
    df["On Progress"] = df[DOCS].eq("On Progress").sum(axis=1).astype(int)
    df["Pending"] = df[DOCS].eq("Pending").sum(axis=1).astype(int)

    df["Progress (%)"] = (
        (df["Done"] + df["On Progress"] * 0.5) / len(DOCS) * 100
    ).round(1)

    # Status satu pengadaan: "Selesai" hanya jika SEMUA 12 dokumen hijau
    df["Status Pengadaan"] = [
        procurement_status_from_counts(int(d), int(o), len(DOCS))
        for d, o in zip(df["Done"], df["On Progress"])
    ]

    # ----------------------------------------------
    # NOMOR URUT
    # ----------------------------------------------

    no_source = source_cols["No"]

    if no_source is not None:
        nomor = pd.to_numeric(df[no_source], errors="coerce")
        nomor = nomor.fillna(
            pd.Series(range(1, len(df) + 1), index=df.index)
        )
        df["No"] = nomor.astype(int)
    else:
        df["No"] = list(range(1, len(df) + 1))

    # ----------------------------------------------
    # TANGGAL TOR, REQUEST, DAN PENGADAAN SELESAI
    # ----------------------------------------------

    def date_column(canonical):
        source = source_cols[canonical]

        if source is None:
            return [None] * len(df)

        return [parse_date(v, date_order) for v in df[source]]

    df["Tgl TOR"] = pd.Series(date_column("Tanggal TOR"), dtype="object")
    df["Tgl Request"] = pd.Series(
        date_column("Tanggal Request"), dtype="object"
    )
    df["Tgl Selesai"] = pd.Series(
        date_column("Tanggal Selesai"), dtype="object"
    )

    # ----------------------------------------------
    # CATAT WAITING TIME KE SPREADSHEET
    # (kegagalan menulis tidak boleh merusak dashboard)
    # ----------------------------------------------

    sync_info = {"status": "off", "written": 0, "message": ""}

    if get_write_enabled():

        try:
            sync_info = sync_waiting_times(
                df=df,
                headers=headers,
                values=values,
                spreadsheet_id=spreadsheet_id,
                range_name=range_name,
                today=today_wib(),
                write_format=get_write_format(),
                has_tor=source_cols["Tanggal TOR"] is not None,
                has_request=source_cols["Tanggal Request"] is not None
            )

        except HttpError as error:

            status_code = getattr(getattr(error, "resp", None), "status", None)

            if status_code == 403:
                message = (
                    "Dashboard tidak punya izin menulis ke spreadsheet. "
                    "Bagikan spreadsheet ke email service account "
                    "dengan akses Editor."
                )
            else:
                message = "Gagal menulis waiting time: {}".format(error)

            sync_info = {"status": "error", "written": 0, "message": message}

        except Exception as error:

            sync_info = {
                "status": "error",
                "written": 0,
                "message": "Gagal menulis waiting time: {}".format(error)
            }

    info = {
        "number_row_sheet": (
            (number_row + 1) if number_row is not None else None
        ),
        "header_row_sheet": header_row + 1,
        "has_tor": source_cols["Tanggal TOR"] is not None,
        "has_request": source_cols["Tanggal Request"] is not None,
        "has_selesai": source_cols["Tanggal Selesai"] is not None,
        "detected": {
            key: source_cols[key]
            for key in ["Tanggal TOR", "Tanggal Request", "Tanggal Selesai"]
        },
        "date_order": date_order,
        "sync": sync_info,
    }

    return df, info


# ==================================================
# KOMPONEN TAMPILAN
# ==================================================

# ---------- Ikon (SVG sebaris) ----------

ICON_PATHS = {
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "pie": '<path d="M21 15.5A9 9 0 1 1 8.5 3"/><path d="M21 12A9 9 0 0 0 12 3v9z"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "list": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3v3h6V3M9 12h6M9 16h4"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "building": '<rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
    "tag": '<path d="M20 12l-8 8a2 2 0 0 1-2.8 0l-5-5a2 2 0 0 1 0-2.8L12 4h8z"/><circle cx="16" cy="8" r="1"/>',
    "hourglass": '<path d="M7 3h10M7 21h10M8 3v4l4 5-4 5v4M16 3v4l-4 5 4 5v4"/>',
    "timer": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/>',
    "bars": '<path d="M5 20v-8M12 20V4M19 20v-5"/>',
    "card": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/>',
    "coin": '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.5 0-2.5.8-2.5 2s1 1.7 2.5 2 2.5.8 2.5 2-1 2-2.5 2c-1 0-2-.5-2.5-1.5M12 6.5V8m0 8v1.5"/>',
}


def icon_svg(name, size=18):
    path = ICON_PATHS.get(name)

    if not path:
        return ""

    return (
        '<svg class="ico" width="{size}" height="{size}" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '{path}</svg>'
    ).format(size=size, path=path)


# ---------- Header (logo + judul) ----------

def logo_img_html(filename, alt):
    """Tag <img> logo. Kosong bila file gambar tidak ditemukan."""
    src = image_data_uri(filename)

    if not src:
        return ""

    return '<img class="app-logo" src="{}" alt="{}">'.format(src, esc(alt))


def header_html(updated_text):
    """Header: logo BRI (kiri) | judul + keterangan (tengah) | logo DWI (kanan)."""
    return (
        '<div class="app-header">'
        '<div class="hdr-left">{logo_left}</div>'
        '<div class="hdr-center">'
        '<div class="app-title">'
        '<span class="app-title-text">DASHBOARD MONITORING PENGADAAN</span>'
        '</div>'
        '<div class="app-subtitle">{subtitle}</div>'
        '</div>'
        '<div class="hdr-right">{logo_right}</div>'
        '</div>'
    ).format(
        logo_left=logo_img_html(LOGO_LEFT_FILE, LOGO_LEFT_ALT),
        subtitle=esc(
            "Monitoring progres dan kelengkapan dokumen pengadaan  •  "
            "Diperbarui: {}".format(updated_text)
        ),
        logo_right=logo_img_html(LOGO_RIGHT_FILE, LOGO_RIGHT_ALT),
    )


# ---------- Kartu ----------

def kpi_card(label, value, sub="", accent=BRAND_PRIMARY, icon="", value_color=""):
    chip = (
        '<span class="chip">{}</span>'.format(icon_svg(icon, 16))
        if icon else ""
    )

    value_style = (
        ' style="color:{};"'.format(value_color) if value_color else ""
    )

    return (
        '<div class="kpi" style="--accent:{accent};">'
        '<div class="label">{chip}<span>{label}</span></div>'
        '<div class="value"{value_style}>{value}</div>'
        '<div class="sub">{sub}</div>'
        '</div>'
    ).format(
        accent=accent,
        chip=chip,
        label=esc(label),
        value_style=value_style,
        value=esc(value),
        sub=esc(sub) if sub else "&nbsp;"
    )


def kpi_wide_card(label, value, sub, accent, icon):
    """Kartu KPI lebar dengan ikon bulat di kiri (untuk waiting time)."""
    return (
        '<div class="kpi kpi-wide" style="--accent:{accent};">'
        '<div class="big-icon">{icon}</div>'
        '<div class="kw-body">'
        '<div class="label"><span>{label}</span></div>'
        '<div class="value">{value}</div>'
        '<div class="sub">{sub}</div>'
        '</div>'
        '</div>'
    ).format(
        accent=accent,
        icon=icon_svg(icon, 24),
        label=esc(label),
        value=esc(value),
        sub=esc(sub) if sub else "&nbsp;"
    )


def info_card(label, value, icon="", accent=BRAND_PRIMARY):
    chip = (
        '<span class="chip chip-lg">{}</span>'.format(icon_svg(icon, 20))
        if icon else ""
    )

    return (
        '<div class="info-card" style="--accent:{accent};">'
        '{chip}'
        '<div>'
        '<div class="label">{label}</div>'
        '<div class="value">{value}</div>'
        '</div>'
        '</div>'
    ).format(
        accent=accent,
        chip=chip,
        label=esc(label),
        value=esc(value)
    )


def status_pill(text):
    return (
        '<div class="status-pill">'
        '<span class="status-dot"></span>{}'
        '</div>'
    ).format(esc(text))


def doc_cards_html(row):
    cards = []

    for number, doc in enumerate(DOCS, start=1):
        status = row[doc]

        css = {
            "Done": "done",
            "On Progress": "progress",
            "Pending": "pending"
        }.get(status, "pending")

        cards.append(
            '<div class="doc-card {css}">'
            '<div class="doc-no">{number}</div>'
            '<div>'
            '<div class="doc-name">{name}</div>'
            '<span class="pill {pill}">{status}</span>'
            '</div>'
            '</div>'.format(
                css=css,
                number=number,
                name=esc(doc),
                pill=PILL_CLASS.get(status, "pill-pending"),
                status=esc(DOC_STATUS_LABEL.get(status, status))
            )
        )

    return '<div class="doc-grid">{}</div>'.format("".join(cards))


def short_label(text, limit=34):
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def wrap_label(text, width=36):
    """
    Pecah label panjang menjadi beberapa baris (pakai <br>) agar nama
    dokumen tampil LENGKAP di sumbu grafik, tidak terpotong dan tidak
    memakai tanda "…". Dipakai untuk label sumbu Y pada grafik Plotly.
    """
    lines = textwrap.wrap(
        str(text),
        width=width,
        break_long_words=False,
        break_on_hyphens=False
    )

    return "<br>".join(lines) if lines else str(text)


def refresh_data():
    """
    Hapus cache data. Fungsi ini dipakai sebagai CALLBACK tombol Refresh
    (on_click), jadi berjalan SEBELUM skrip dijalankan ulang oleh
    Streamlit. Sengaja TIDAK memanggil st.rerun():

    Bila st.rerun() dipanggil di tengah skrip (setelah tombol, tetapi
    SEBELUM menu st.radio dibuat), Streamlit menganggap widget menu
    tidak ikut dirender pada jalannya skrip itu lalu MENGHAPUS nilainya
    dari session_state. Akibatnya menu kembali ke "Ringkasan" (tabel
    pengadaan muncul) padahal di layar menu yang menyala masih
    "Pembayaran". Dengan callback, tidak ada skrip yang terpotong
    sehingga nilai menu tetap terjaga.
    """
    st.cache_data.clear()


def render_nav():
    """
    Tombol Refresh + menu utama. Dipanggil TEPAT SATU KALI per jalannya
    aplikasi dan SELALU yang PERTAMA (sebelum data dibaca), di dalam
    wadah nav_box yang letaknya di bawah filter & kartu. Dengan begitu:
      - nilai menu yang dipakai halaman = nilai yang dikembalikan widget
        pada jalannya aplikasi yang sama (tidak ada selisih antara menu
        yang tampak aktif dan isi halaman);
      - menu tidak pernah hilang walau pembacaan data gagal / st.stop().

    Tombol Refresh memakai on_click=refresh_data (bukan st.rerun()),
    supaya skrip tidak terpotong sebelum menu dibuat (lihat refresh_data).

    Tombol dirender tepat sebelum menu. Lewat CSS (.st-key-refresh_btn)
    wadah tombol dibuat selebar penuh & setinggi 0, lalu tombolnya
    diposisikan di sisi KANAN baris menu dengan ukuran yang sama seperti
    menu (tinggi 40px, bentuk pil). Bila posisinya kurang pas secara
    vertikal, ubah nilai --refresh-top di blok :root pada CSS.
    Di layar sempit (<= 1100px) tombol tampil di atas menu.
    """
    st.button(
        "🔄 Refresh Data",
        key="refresh_btn",
        on_click=refresh_data
    )

    return st.radio(
        "Menu",
        MENU_ITEMS,
        horizontal=True,
        key=MENU_KEY,
        label_visibility="collapsed"
    )


def footer_caption():
    st.write("")

    st.caption(
        "Keterangan warna sel di Google Sheets:  "
        "🟩 Hijau = Selesai   |   🟨 Kuning = Berjalan   |   ⬜ Putih = Belum Mulai"
    )


# ---------- Tabel Daftar Pengadaan (kelengkapan dokumen 1-12) ----------

def doc_status_cell(status, doc_name):
    """
    Satu sel kelengkapan dokumen:
      hijau  -> centang hijau
      kuning -> bulat kuning
      putih  -> kosong
    """
    label = DOC_STATUS_LABEL.get(status, status)
    tooltip = esc("{} - {}".format(doc_name, label))

    if status == "Done":
        content = '<span class="chk">&#10003;</span>'
    elif status == "On Progress":
        content = '<span class="dot"></span>'
    else:
        content = ""

    return '<td class="dc" title="{}">{}</td>'.format(tooltip, content)


def progress_cell(value, extra_class=""):
    """
    Sel progres. `extra_class` dipakai tabel pembayaran untuk
    mengunci kolom ini di sisi kanan (class "s4").
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0

    width = min(max(number, 0.0), 100.0)

    css = "c-prog" + (" " + extra_class if extra_class else "")

    return (
        '<td class="{css}">'
        '<div class="pg-wrap">'
        '<div class="pg-bar"><div style="width:{width:.1f}%;"></div></div>'
        '<span class="pg-text">{number:.1f}%</span>'
        '</div>'
        '</td>'
    ).format(css=css, width=width, number=number)


def procurement_table_html(data):
    """Tabel HTML dengan header bertingkat 'Kelengkapan Dokumen' (1-12)."""

    head_top = (
        '<tr class="h1">'
        '<th rowspan="2" style="width:44px;">No</th>'
        '<th rowspan="2" class="th-left">Nama Pengadaan</th>'
        '<th rowspan="2">Tipe</th>'
        '<th rowspan="2">PIC</th>'
        '<th colspan="{count}">Kelengkapan Dokumen</th>'
        '<th rowspan="2">Progres</th>'
        '</tr>'
    ).format(count=len(DOCS))

    head_numbers = "".join(
        '<th title="{title}">{number}</th>'.format(
            title=esc(doc),
            number=number
        )
        for number, doc in enumerate(DOCS, start=1)
    )

    head = '<thead>{}<tr class="h2">{}</tr></thead>'.format(
        head_top, head_numbers
    )

    body_rows = []

    for _, item in data.iterrows():

        cells = [
            '<td class="c-no">{}</td>'.format(int(item["No"])),
            '<td class="c-name">{}</td>'.format(esc(item["Nama Pengadaan"])),
            '<td class="c-tipe">{}</td>'.format(esc(item["Tipe"])),
            '<td class="c-pic">{}</td>'.format(esc(item["PIC"])),
        ]

        for doc in DOCS:
            cells.append(doc_status_cell(item[doc], doc))

        cells.append(progress_cell(item["Progress (%)"]))

        body_rows.append("<tr>{}</tr>".format("".join(cells)))

    return (
        '<div class="tbl-wrap">'
        '<table class="proc-table">{head}<tbody>{body}</tbody></table>'
        '</div>'
    ).format(head=head, body="".join(body_rows))


def document_legend_html():
    """Keterangan nomor dokumen 1-12 dan arti ikon."""

    items = "".join(
        '<div class="legend-item">'
        '<span class="legend-no">{number}</span>'
        '<span>{name}</span>'
        '</div>'.format(number=number, name=esc(doc))
        for number, doc in enumerate(DOCS, start=1)
    )

    status = (
        '<div class="legend-status">'
        '<span><span class="chk">&#10003;</span> Selesai (sel hijau)</span>'
        '<span><span class="dot"></span> Berjalan (sel kuning)</span>'
        '<span><span class="empty-box"></span> Belum Mulai (sel putih)</span>'
        '</div>'
    )

    return (
        '<div class="legend-box">'
        '<div class="legend-title">Keterangan Kelengkapan Dokumen</div>'
        '<div class="legend-grid">{items}</div>'
        '{status}'
        '</div>'
    ).format(items=items, status=status)


# ==================================================
# PEMBAYARAN PENGADAAN (worksheet Sheet2)
# ==================================================

# ---------- Pembaca nilai ----------

def parse_money(text):
    """
    Teks rupiah -> angka. Contoh: "Rp155,844" -> 155844.0.
    Pemisah ribuan (koma/titik) dikenali otomatis.
    Return None bila tidak ada angka.
    """
    if text is None:
        return None

    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)

    cleaned = re.sub(r"[^0-9.,\-]", "", str(text))

    if not re.search(r"\d", cleaned):
        return None

    negative = cleaned.startswith("-")
    cleaned = cleaned.replace("-", "")

    if "," in cleaned and "." in cleaned:
        decimal = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousand = "." if decimal == "," else ","
        cleaned = cleaned.replace(thousand, "").replace(decimal, ".")
    elif "," in cleaned or "." in cleaned:
        separator = "," if "," in cleaned else "."
        parts = cleaned.split(separator)

        if len(parts) > 2 or len(parts[-1]) == 3:
            cleaned = cleaned.replace(separator, "")
        else:
            cleaned = cleaned.replace(separator, ".")

    try:
        value = float(cleaned)
    except ValueError:
        return None

    return -value if negative else value


def parse_int(text):
    """Angka bulat pertama dalam teks ("6" -> 6). 0 bila tidak ada."""
    match = re.search(r"\d+", str(text))
    return int(match.group()) if match else 0


# Singkatan bulan Indonesia -> Inggris (agar dibaca strptime)
ID_MONTH_FIX = {
    "agu": "Aug",
    "agt": "Aug",
    "ags": "Aug",
    "okt": "Oct",
    "des": "Dec",
    "mei": "May",
}


def parse_payment_date(text):
    """
    Tanggal sheet pembayaran, mis. "20-Jul-26" atau "5-Oct-2026".
    Format angka biasa (9/29/2026, 2026-09-29) tetap dibaca.
    """
    if text is None:
        return None

    parsed = parse_date(text, get_date_order())

    if parsed is not None:
        return parsed

    value = str(text).strip()

    if not value or value == "-":
        return None

    for source, target in ID_MONTH_FIX.items():
        value = re.sub(
            r"\b{}\b".format(source), target, value, flags=re.IGNORECASE
        )

    for fmt in (
        "%d-%b-%y", "%d-%b-%Y", "%d %b %y", "%d/%b/%Y",
        "%d-%B-%Y", "%d %B %Y"
    ):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def shift_month(year, month, delta):
    """(tahun, bulan) digeser `delta` bulan. Aman melewati pergantian tahun."""
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def month_label(year, month):
    return "{} {}".format(MONTH_NAMES[month - 1], year)


def format_rp(value):
    """Angka -> "Rp155,844" (sama seperti tampilan di spreadsheet)."""
    if value is None:
        return "-"
    return "Rp{:,.0f}".format(value)


def cell_text(row, index):
    """Isi sel sebagai teks. Kosong bila indeks di luar baris / None."""
    if index is None or index >= len(row):
        return ""
    return str(row[index])


# ---------- Deteksi struktur sheet pembayaran ----------

def find_payment_header(values):
    """
    Cari struktur header sheet pembayaran.

    - Baris "Project" dan baris "Tanggal SPK" (bisa berbeda karena header
      bertingkat).
    - Baris nama bulan: baris (dari 15 baris pertama) yang berisi nama
      bulan paling banyak. Baris ini bisa berbeda dari baris "Project".

    Return dict:
      first      : baris pertama blok header
      last       : baris terakhir blok header (data mulai last + 1)
      month_row  : baris nama bulan (None bila tidak ada)
    atau None bila baris "Project" / "Tanggal SPK" tidak ditemukan.
    """
    project_row = None
    spk_row = None

    for i, row in enumerate(values[:15]):
        keys = [norm(c) for c in row]

        if project_row is None and "project" in keys:
            project_row = i

        if spk_row is None and "tanggalspk" in keys:
            spk_row = i

    info_rows = [r for r in (project_row, spk_row) if r is not None]

    if not info_rows:
        return None

    # Baris nama bulan = baris dengan jumlah nama bulan terbanyak
    month_row = None
    best = 0

    for i, row in enumerate(values[:15]):
        count = sum(1 for c in row if norm(c) in MONTH_LOOKUP)

        if count > best:
            best = count
            month_row = i

    rows = list(info_rows)

    if month_row is not None:
        rows.append(month_row)

    return {
        "first": min(rows),
        "last": max(rows),
        "month_row": month_row,
    }


def year_of(text):
    """Tahun 4 digit (2000-2099) dari teks sel, atau None."""
    match = re.fullmatch(r"(20\d\d)(\.0)?", norm(text))
    return int(match.group(1)) if match else None


def detect_month_columns(values, first, last):
    """
    Cari kolom bulan pembayaran dari baris header `first`..`last`.

    Tahun diambil dari sel tahun (2026, 2027, ...) dan berlaku ke kanan
    sampai ada tahun berikutnya. Bila sel tahun tidak ada, tahun naik
    otomatis saat nama bulan kembali ke awal (Desember -> Januari).
    Kolom "Tanggal Pembayaran FMA ..." dipasangkan ke bulan di kirinya.

    Return list: {"year", "month", "col", "fma_col"}
    """
    width = max((len(values[r]) for r in range(first, last + 1)), default=0)

    months = []
    year = None
    last_month = 0
    explicit_year = False

    for c in range(width):

        texts = [
            norm(values[r][c]) if c < len(values[r]) else ""
            for r in range(first, last + 1)
        ]

        for text in texts:
            found = year_of(text)
            if found:
                year = found
                explicit_year = True

        month = next(
            (MONTH_LOOKUP[t] for t in texts if t in MONTH_LOOKUP),
            None
        )

        if month is not None:

            if year is None:
                year = today_wib().year
            elif not explicit_year and month <= last_month:
                year += 1

            months.append({
                "year": year,
                "month": month,
                "col": c,
                "fma_col": None
            })

            last_month = month
            explicit_year = False
            continue

        is_fma = any(
            "fma" in t or "tanggalpembayaran" in t for t in texts
        )

        if is_fma and months and months[-1]["fma_col"] is None:
            months[-1]["fma_col"] = c

    return months


# ---------- Membentuk data pembayaran per pengadaan ----------

def parse_payment_sheet(values, grid):
    """
    Ubah isi sheet pembayaran (teks + warna sel) menjadi daftar pengadaan.

    Tiap pengadaan (hanya status Running) berisi:
      schedule : daftar cicilan berurutan {year, month, amount, status, fma}
      cells    : {(tahun, bulan): cicilan} khusus bulan yang ada di sheet
      paid / proses / total / progress / pay_status, dst.

    Return: (records, months, info)
    """
    header = find_payment_header(values)

    if header is None:
        raise ValueError(
            "Baris header 'Project' / 'Tanggal SPK' tidak ditemukan "
            "pada sheet pembayaran."
        )

    first = header["first"]
    last = header["last"]
    month_row = header["month_row"]

    headers = build_headers(values, first, last)

   
    if month_row is not None:
        scan_first = max(min(first, month_row) - 1, 0)
        months = detect_month_columns(values, scan_first, last)
    else:
        months = []


    limit = months[0]["col"] if months else len(headers)
    info_headers = headers[:limit]

    def column(key, fuzzy=True):
        found = find_col(info_headers, PAY_COLUMN_ALIASES[key], fuzzy=fuzzy)
        return info_headers.index(found) if found is not None else None

    c_jenis = column("Jenis")
    c_name = column("Nama")
    c_spk = column("SPK")
    c_nilai = column("Nilai")
    c_status = column("Status")
    c_durasi = column("Durasi")

    if c_name is None:
        raise ValueError("Kolom 'Project' tidak ditemukan pada sheet pembayaran.")

    records = []

    for r in range(last + 1, len(values)):

        row = values[r]

        if is_ket_row(row):
            break

        name = cell_text(row, c_name).strip().strip('"').strip()

        if not name or name == "-":
            continue

        # Hanya pengadaan berstatus Running
        if c_status is not None:
            if norm(cell_text(row, c_status)) != PAY_RUNNING_STATUS:
                continue

        grid_cells = grid[r].get("values", []) if r < len(grid) else []

        # ----- cicilan yang ada di sheet (per kolom bulan) -----
        schedule = []

        for month in months:

            col = month["col"]
            amount_text = cell_text(row, col).strip()
            status = (
                get_status(grid_cells[col])
                if col < len(grid_cells)
                else "Pending"
            )

            # Bulan tanpa angka dan tanpa warna = bukan bulan cicilan
            if amount_text in {"", "-"} and status == "Pending":
                continue

            fma_text = cell_text(row, month["fma_col"]).strip()

            if fma_text == "-":
                fma_text = ""

            schedule.append({
                "year": month["year"],
                "month": month["month"],
                "amount": parse_money(amount_text),
                "status": status,
                "fma": parse_payment_date(fma_text),
                "fma_text": fma_text,
                "in_sheet": True,
            })

        cells = {(e["year"], e["month"]): e for e in schedule}

        # ----- identitas pengadaan -----
        tgl_spk = parse_payment_date(cell_text(row, c_spk))
        nilai = parse_money(cell_text(row, c_nilai))
        durasi = parse_int(cell_text(row, c_durasi))

        total = max(durasi, len(schedule))

        # Mulai pembayaran = bulan setelah tanggal SPK
        if tgl_spk is not None:
            start = shift_month(tgl_spk.year, tgl_spk.month, 1)
        elif schedule:
            start = (schedule[0]["year"], schedule[0]["month"])
        else:
            start = None

        # Cicilan yang jatuh di luar kolom sheet (mis. durasi 12 bulan tetapi
        # kolom bulan baru sampai September) ditambahkan sebagai belum mulai.
        if schedule:
            following = shift_month(
                schedule[-1]["year"], schedule[-1]["month"], 1
            )
        else:
            following = start

        while following is not None and len(schedule) < total:
            schedule.append({
                "year": following[0],
                "month": following[1],
                "amount": None,
                "status": "Pending",
                "fma": None,
                "fma_text": "",
                "in_sheet": False,
            })
            following = shift_month(following[0], following[1], 1)

        # ----- hitungan pembayaran -----
        paid = sum(1 for e in schedule if e["status"] == "Done")
        proses = sum(1 for e in schedule if e["status"] == "On Progress")

        paid_amount = sum(
            e["amount"] or 0 for e in schedule if e["status"] == "Done"
        )
        proses_amount = sum(
            e["amount"] or 0 for e in schedule if e["status"] == "On Progress"
        )

        if total == 0:
            pay_status = "Belum Mulai"
        else:
            pay_status = procurement_status_from_counts(paid, proses, total)

        # Nomor urut dibuat sendiri (1, 2, 3, ...), tidak mengikuti kolom
        # No di sheet karena baris non-Running dilewati dan nomornya loncat.
        records.append({
            "no": len(records) + 1,
            "jenis": cell_text(row, c_jenis).strip() or "-",
            "nama": name,
            "tgl_spk": tgl_spk,
            "nilai": nilai,
            "durasi": durasi,
            "total": total,
            "start": start,
            "end": (
                (schedule[-1]["year"], schedule[-1]["month"])
                if schedule else None
            ),
            "schedule": schedule,
            "cells": cells,
            "paid": paid,
            "proses": proses,
            "paid_amount": paid_amount,
            "proses_amount": proses_amount,
            "progress": round(paid / total * 100, 1) if total else 0.0,
            "pay_status": pay_status,
        })

    info = {
        "has_status": c_status is not None,
        "has_spk": c_spk is not None,
        "has_nilai": c_nilai is not None,
        "month_count": len(months),
        "month_row_sheet": (month_row + 1) if month_row is not None else None,
        "header_row_sheet": first + 1,
        "data_row_sheet": last + 2,
    }

    return records, months, info


# ---------- Membaca sheet pembayaran dari Google Sheets ----------

def fetch_cell_grid(spreadsheet_id, range_name, row_count):
    """Format (warna) semua sel pada sheet, per baris."""

    def fetch_colors():
        service = build(
            "sheets",
            "v4",
            credentials=get_credentials(),
            cache_discovery=False
        )

        return service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=["{}!A1:BZ{}".format(range_name, row_count)],
            includeGridData=True,
            fields=(
                "sheets(properties(title),"
                "data(rowData(values("
                "effectiveFormat(backgroundColor),"
                "userEnteredFormat(backgroundColor)))))"
            )
        ).execute(num_retries=3)

    response = with_retry(fetch_colors)

    sheet_data = response["sheets"][0]

    return sheet_data.get("data", [{}])[0].get("rowData", [])


@st.cache_data(ttl=30)
def load_payment_data():

    spreadsheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
    sheet_name = get_setting("payment_worksheet_name", PAY_SHEET_DEFAULT)

    def fetch_values():
        client = connect_google()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet.get_all_values()

    values = with_retry(fetch_values)

    if not values:
        return [], [], {"has_status": True}

    if str(sheet_name).replace("_", "").isalnum():
        range_name = str(sheet_name)
    else:
        range_name = "'{}'".format(str(sheet_name).replace("'", "''"))

    grid = fetch_cell_grid(spreadsheet_id, range_name, len(values))

    return parse_payment_sheet(values, grid)



def render_payment_filters(records, box):
    """Filter khusus pembayaran (ditaruh di wadah `box`). Return (cari, tahun, status)."""

    # Tahun yang tersedia = tahun MULAI pembayaran tiap pengadaan
    years = sorted({r["start"][0] for r in records if r["start"]})

    with box:
        p1, p2, p3, _spare1, _spare2 = st.columns([2.2, 1, 1, 1, 1])

    search = p1.text_input(
        "Cari pengadaan",
        placeholder="Ketik nama pengadaan...",
        key="pay_search"
    )

    year_choice = p2.selectbox(
        "Tahun Mulai Pembayaran",
        ["Semua"] + [str(y) for y in years],
        key="pay_year"
    )

    status_choice = p3.selectbox(
        "Status Pembayaran",
        ["Semua"] + STATUS_ORDER,
        key="pay_status"
    )

    return search, year_choice, status_choice


def apply_payment_filters(records, search, year_choice, status_choice):

    shown = list(records)

    if search.strip():
        keyword = search.strip().lower()
        shown = [r for r in shown if keyword in r["nama"].lower()]

    if year_choice != "Semua":
        year = int(year_choice)
        shown = [
            r for r in shown
            if r["start"] and r["start"][0] == year
        ]

    if status_choice != "Semua":
        shown = [r for r in shown if r["pay_status"] == status_choice]

    # Nomor urut ulang 1..n sesuai hasil filter
    return [dict(r, no=i) for i, r in enumerate(shown, start=1)]


def render_payment_kpis(shown, box):
    """
    Kartu ringkasan pembayaran (sama susunannya dengan kartu pengadaan):
    Total, Selesai, Berjalan, Belum Mulai, Progres.

    Hijau = Selesai (dibayar), Kuning = Berjalan (diproses),
    Putih = Belum Mulai. Angka besar = jumlah pengadaan pada status itu;
    keterangan kecil = jumlah cicilan per warna.
    """
    total = len(shown)

    n_selesai = sum(1 for r in shown if r["pay_status"] == "Selesai")
    n_berjalan = sum(1 for r in shown if r["pay_status"] == "Berjalan")
    n_belum = sum(1 for r in shown if r["pay_status"] == "Belum Mulai")

    cicilan_total = sum(r["total"] for r in shown)
    cicilan_paid = sum(r["paid"] for r in shown)
    cicilan_proses = sum(r["proses"] for r in shown)
    cicilan_belum = max(cicilan_total - cicilan_paid - cicilan_proses, 0)

    overall = cicilan_paid / cicilan_total * 100 if cicilan_total else 0.0

    with box:
        k1, k2, k3, k4, k5 = st.columns(5)

    k1.markdown(
        kpi_card(
            "Total Pembayaran",
            total,
            "{} cicilan (status Running)".format(cicilan_total),
            BRAND_PRIMARY,
            icon="card"
        ),
        unsafe_allow_html=True
    )
    k2.markdown(
        kpi_card(
            "Selesai",
            n_selesai,
            "{} Cicilan Dibayar".format(cicilan_paid),
            BRAND_PRIMARY,
            icon="check"
        ),
        unsafe_allow_html=True
    )
    k3.markdown(
        kpi_card(
            "Berjalan",
            n_berjalan,
            "{} Cicilan Diproses".format(cicilan_proses),
            BRAND_PRIMARY,
            icon="clock"
        ),
        unsafe_allow_html=True
    )
    k4.markdown(
        kpi_card(
            "Belum Mulai",
            n_belum,
            "{} Cicilan Belum Mulai".format(cicilan_belum),
            BRAND_PRIMARY,
            icon="list"
        ),
        unsafe_allow_html=True
    )
    k5.markdown(
        kpi_card(
            "Progres Pembayaran",
            "{:.1f}%".format(overall),
            "{} dari {} cicilan dibayar".format(cicilan_paid, cicilan_total),
            BRAND_PRIMARY,
            icon="pie"
        ),
        unsafe_allow_html=True
    )


# ---------- Tabel Pembayaran Pengadaan ----------

def payment_status_cell(entry, month):
    """
    Satu sel cicilan pada bulan tertentu:
      hijau  -> centang hijau
      kuning -> bulat kuning
      putih  -> lingkaran kosong (bulan cicilan, belum mulai)
      bukan bulan cicilan -> sel kosong
    """
    if entry is None:
        return '<td class="dc"></td>'

    status = entry["status"]
    label = PAY_STATUS_LABEL.get(status, status)

    tooltip = "{} - {}".format(
        month_label(month["year"], month["month"]), label
    )

    if entry["amount"] is not None:
        tooltip += " - {}".format(format_rp(entry["amount"]))

    if status == "Done":
        content = '<span class="chk">&#10003;</span>'
    elif status == "On Progress":
        content = '<span class="dot"></span>'
    else:
        content = '<span class="empty-box"></span>'

    return '<td class="dc" title="{}">{}</td>'.format(esc(tooltip), content)


def payment_table_html(records, months):
    """
    Tabel HTML pembayaran dengan header bertingkat:
    Pembayaran -> tahun -> bulan.

    Kolom No, Nama Pengadaan, dan Mulai Pembayaran dikunci di kiri
    (class s1, s2, s3), kolom Progres dikunci di kanan (class s4).
    Hanya kolom tahun/bulan yang ikut bergeser saat di-scroll horizontal.
    (Di HP, hanya No dan Nama yang dikunci; lihat blok RESPONSIF di CSS.)
    """
    year_groups = []

    for month in months:
        if year_groups and year_groups[-1][0] == month["year"]:
            year_groups[-1][1] += 1
        else:
            year_groups.append([month["year"], 1])

    head_top = (
        '<tr class="h1">'
        '<th rowspan="3" class="s1">No</th>'
        '<th rowspan="3" class="th-left s2">Nama Pengadaan</th>'
        '<th rowspan="3" class="s3">Mulai Pembayaran</th>'
        '<th colspan="{count}">Pembayaran</th>'
        '<th rowspan="3" class="s4">Progres</th>'
        '</tr>'
    ).format(count=len(months))

    head_years = '<tr class="h2">{}</tr>'.format(
        "".join(
            '<th colspan="{}">{}</th>'.format(count, year)
            for year, count in year_groups
        )
    )

    head_months = '<tr class="h3">{}</tr>'.format(
        "".join(
            '<th title="{title}">{abbr}</th>'.format(
                title=esc(month_label(m["year"], m["month"])),
                abbr=MONTH_ABBR[m["month"] - 1]
            )
            for m in months
        )
    )

    head = '<thead>{}{}{}</thead>'.format(head_top, head_years, head_months)

    body_rows = []

    for rec in records:

        start_text = (
            month_label(*rec["start"]) if rec["start"] else "-"
        )

        cells = [
            '<td class="c-no s1">{}</td>'.format(int(rec["no"])),
            '<td class="c-name s2">{}</td>'.format(esc(rec["nama"])),
            '<td class="c-start s3">{}</td>'.format(esc(start_text)),
        ]

        for month in months:
            entry = rec["cells"].get((month["year"], month["month"]))
            cells.append(payment_status_cell(entry, month))

        cells.append(progress_cell(rec["progress"], "s4"))

        body_rows.append("<tr>{}</tr>".format("".join(cells)))

    return (
        '<div class="tbl-wrap">'
        '<table class="proc-table pay-table">{head}<tbody>{body}</tbody></table>'
        '</div>'
    ).format(head=head, body="".join(body_rows))


def payment_legend_html():
    """Keterangan arti ikon pada tabel pembayaran."""

    status = (
        '<div class="legend-status solo">'
        '<span><span class="chk">&#10003;</span> Selesai / Dibayar (sel hijau)</span>'
        '<span><span class="dot"></span> Berjalan / Diproses (sel kuning)</span>'
        '<span><span class="empty-box"></span> Belum Mulai (sel putih)</span>'
        '<span>Sel kosong = bukan bulan cicilan</span>'
        '</div>'
    )

    return (
        '<div class="legend-box">'
        '<div class="legend-title">Keterangan Status Pembayaran</div>'
        '{status}'
        '</div>'
    ).format(status=status)


def render_payment_list(shown, months):
    """Isi menu 'Pembayaran Pengadaan': tabel + keterangan."""

    st.markdown(
        '<div class="section-title">Daftar Pembayaran Pengadaan</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        payment_table_html(shown, months),
        unsafe_allow_html=True
    )

    st.markdown(payment_legend_html(), unsafe_allow_html=True)



# ---------- Detail Pembayaran Pengadaan ----------

def schedule_columns(count):
    """
    Jumlah kolom kartu jadwal agar susunannya selalu rapi (baris terakhir
    tidak menyisakan banyak ruang kosong):
      1-4 cicilan -> sebanyak cicilan (1 baris)
      5   cicilan -> 5 kolom (1 baris)
      6   cicilan -> 3 kolom (2 baris, 3 + 3)
      7+  cicilan -> 3 sampai 6 kolom dengan sisa kosong paling sedikit
                     (diutamakan 4, lalu 3, 5, 6)
    Di layar sempit, jumlah kolom otomatis dikurangi lewat CSS
    (2 kolom di tablet, 1 kolom di HP).
    """
    if count <= 5:
        return max(count, 1)

    best_cols = 4
    best_empty = None

    for cols in (4, 3, 5, 6):
        empty = (-count) % cols

        if best_empty is None or empty < best_empty:
            best_cols = cols
            best_empty = empty

    return best_cols


def payment_schedule_html(schedule):
    """
    Kartu jadwal pembayaran per bulan. Setiap kartu berisi: nomor + bulan,
    nilai cicilan, tanggal FMA, dan status. Jumlah kolom mengikuti jumlah
    cicilan (lihat schedule_columns).
    """
    if not schedule:
        return '<div class="doc-meta">Belum ada jadwal pembayaran.</div>'

    cards = []

    for number, entry in enumerate(schedule, start=1):

        status = entry["status"]

        css = {
            "Done": "done",
            "On Progress": "progress",
            "Pending": "pending"
        }.get(status, "pending")

        if entry["fma"] is not None:
            fma = fmt_date(entry["fma"])
        elif entry["fma_text"]:
            fma = entry["fma_text"]
        else:
            fma = "Belum ada"

        cards.append(
            '<div class="pay-card {css}">'
            '<div class="pay-head">'
            '<span class="pay-no">{number}</span>'
            '<span class="pay-month">{month}</span>'
            '</div>'
            '<div class="pay-amount">{amount}</div>'
            '<div class="pay-meta">'
            '<span class="pay-meta-label">Tanggal FMA</span>'
            '<span class="pay-meta-value">{fma}</span>'
            '</div>'
            '<div class="pay-foot">'
            '<span class="pill {pill}">{status}</span>'
            '</div>'
            '</div>'.format(
                css=css,
                number=number,
                month=esc(month_label(entry["year"], entry["month"])),
                amount=esc(format_rp(entry["amount"])),
                fma=esc(fma),
                pill=PILL_CLASS.get(status, "pill-pending"),
                status=esc(PAY_STATUS_LABEL.get(status, status))
            )
        )

    return '<div class="pay-grid" style="--cols:{};">{}</div>'.format(
        schedule_columns(len(schedule)), "".join(cards)
    )


def payment_summary_html(rec):
    """Ringkasan jumlah cicilan per status di atas kartu jadwal."""

    belum = max(rec["total"] - rec["paid"] - rec["proses"], 0)

    return (
        '<div class="pay-summary">'
        '<span class="pill pill-done">Dibayar: {paid}</span>'
        '<span class="pill pill-progress">Diproses: {proses}</span>'
        '<span class="pill pill-pending">Belum Mulai: {belum}</span>'
        '</div>'
    ).format(paid=rec["paid"], proses=rec["proses"], belum=belum)


def render_payment_detail(rec):
    """Detail satu pengadaan: nilai, terbayar, sisa, dan jadwal per bulan."""

    st.markdown(
        '<div class="section-title" style="margin-top:0.6rem;">{}</div>'.format(
            esc(rec["nama"])
        ),
        unsafe_allow_html=True
    )

    # ---------- Info umum ----------

    if rec["start"] and rec["end"]:
        period = "{} – {}".format(
            month_label(*rec["start"]), month_label(*rec["end"])
        )
    else:
        period = "-"

    i1, i2, i3 = st.columns(3)

    i1.markdown(
        info_card("Jenis", rec["jenis"], "tag", BRAND_PRIMARY),
        unsafe_allow_html=True
    )
    i2.markdown(
        info_card(
            "Tanggal SPK", fmt_date(rec["tgl_spk"]),
            "calendar", BRAND_PRIMARY
        ),
        unsafe_allow_html=True
    )
    i3.markdown(
        info_card("Periode Pembayaran", period, "calendar", BRAND_PRIMARY),
        unsafe_allow_html=True
    )

    st.write("")

    # ---------- Nilai pengadaan, terbayar, sisa ----------

    nilai = rec["nilai"]
    belum = max(nilai - rec["paid_amount"], 0) if nilai is not None else None

    if rec["proses_amount"]:
        belum_sub = "termasuk {} dalam proses".format(
            format_rp(rec["proses_amount"])
        )
    else:
        belum_sub = "{} cicilan tersisa".format(rec["total"] - rec["paid"])

    d1, d2, d3, d4 = st.columns(4)

    d1.markdown(
        kpi_card(
            "Nilai Pengadaan",
            format_rp(nilai),
            "durasi {} bulan".format(rec["total"]),
            BRAND_PRIMARY,
            icon="coin"
        ),
        unsafe_allow_html=True
    )
    d2.markdown(
        kpi_card(
            "Sudah Dibayar",
            format_rp(rec["paid_amount"]),
            "{} dari {} cicilan".format(rec["paid"], rec["total"]),
            BRAND_PRIMARY,
            icon="check"
        ),
        unsafe_allow_html=True
    )
    d3.markdown(
        kpi_card(
            "Belum Dibayar",
            format_rp(belum),
            belum_sub,
            BRAND_PRIMARY,
            icon="clock"
        ),
        unsafe_allow_html=True
    )
    d4.markdown(
        kpi_card(
            "Progres Pembayaran",
            "{:.1f}%".format(rec["progress"]),
            "status: {}".format(rec["pay_status"]),
            BRAND_PRIMARY,
            icon="bars"
        ),
        unsafe_allow_html=True
    )

    st.write("")

    # ---------- Progress bar ----------

    st.markdown(
        '<div class="pbar-head">'
        '<span>Progres Pembayaran</span><span>{:.1f}%</span></div>'
        '<div class="pbar"><div style="width:{:.1f}%;"></div></div>'.format(
            rec["progress"],
            min(max(rec["progress"], 0), 100)
        ),
        unsafe_allow_html=True
    )

    # ---------- Jadwal pembayaran per bulan ----------

    st.markdown(
        '<div class="section-title">Jadwal Pembayaran per Bulan</div>',
        unsafe_allow_html=True
    )

    st.markdown(payment_summary_html(rec), unsafe_allow_html=True)

    st.markdown(
        payment_schedule_html(rec["schedule"]),
        unsafe_allow_html=True
    )


def render_payment_detail_page(shown):
    """Isi menu 'Detail Pembayaran': pilih pengadaan lalu tampilkan detail."""

    labels = ["{}. {}".format(int(r["no"]), r["nama"]) for r in shown]

    selected = st.selectbox(
        "Pilih pengadaan",
        labels,
        index=None,
        placeholder="Pilih pengadaan untuk melihat detail pembayaran...",
        key="pay_detail"
    )

    if not selected:

        st.info(
            "Pilih salah satu pengadaan di atas untuk melihat nilai "
            "pengadaan, jumlah dibayar, sisa pembayaran, dan tanggal "
            "pembayaran FMA tiap bulan."
        )

    else:

        render_payment_detail(shown[labels.index(selected)])




st.markdown(
    header_html(datetime.now(WIB).strftime("%d %b %Y, %H:%M")),
    unsafe_allow_html=True
)


notice_box = st.container()
filters_box = st.container()
kpi_box = st.container()
nav_box = st.container()


with nav_box:
    menu = render_nav()



if menu in PAYMENT_MENUS:

    try:

        pay_records, pay_months, pay_info = load_payment_data()

    except Exception as error:

        st.error(
            "Gagal membaca data pembayaran dari Google Sheets. "
            "Periksa nama worksheet (default: Sheet2) dan konfigurasi."
        )

        st.code(str(error))

        st.stop()

    if not pay_info.get("has_status", True):
        st.warning(
            "Kolom 'Status' tidak ditemukan di sheet pembayaran, jadi "
            "semua pengadaan ditampilkan (tidak hanya yang Running)."
        )

    if not pay_months:
        st.warning(
            "Kolom bulan pembayaran (Agustus, September, ...) tidak "
            "ditemukan di sheet pembayaran. Pastikan ada satu baris "
            "header yang berisi nama bulan (Agustus, September, dst.) "
            "di 15 baris pertama worksheet '{}'.".format(
                get_setting("payment_worksheet_name", PAY_SHEET_DEFAULT)
            )
        )
        st.stop()

    if not pay_records:
        st.info("Belum ada pengadaan berstatus Running di sheet pembayaran.")
        st.stop()

    # ---------- Filter pembayaran ----------

    pay_search, pay_year, pay_status = render_payment_filters(
        pay_records, filters_box
    )

    pay_shown = apply_payment_filters(
        pay_records, pay_search, pay_year, pay_status
    )

    if not pay_shown:
        st.info("Tidak ada pembayaran pengadaan yang cocok dengan filter saat ini.")
        st.stop()

    # ---------- Kartu pembayaran ----------

    render_payment_kpis(pay_shown, kpi_box)

    # ---------- Isi menu ----------

    if menu == MENU_PAYMENT:
        render_payment_list(pay_shown, pay_months)
    else:
        render_payment_detail_page(pay_shown)

    footer_caption()

    st.stop()


# ==================================================
# MEMUAT DATA PENGADAAN
# ==================================================

try:

    df, info = load_data()

except Exception as error:

    st.error(
        "Gagal membaca Google Sheets. "
        "Periksa koneksi dan konfigurasi."
    )

    st.code(str(error))

    st.stop()


if df.empty:

    st.warning("Data pengadaan belum tersedia.")

    st.stop()


if info.get("number_row_sheet") is None:

    notice_box.warning(
        "Baris header angka 1–12 untuk kolom dokumen tidak ditemukan. "
        "Dashboard memakai 12 kolom tepat setelah kolom 'Vendor'. "
        "Pastikan header dokumen berisi angka 1 sampai 12."
    )


missing_cols = []

if not info.get("has_tor"):
    missing_cols.append("Tanggal TOR Diterima")
if not info.get("has_request"):
    missing_cols.append("Tanggal Request Pengadaan")
if not info.get("has_selesai"):
    missing_cols.append("Pengadaan Selesai")

if missing_cols:
    notice_box.warning(
        "Kolom berikut tidak ditemukan di spreadsheet: {}. "
        "Waiting time yang terkait tidak dapat dihitung.".format(
            ", ".join(missing_cols)
        )
    )


TODAY = today_wib()


# ==================================================
# FILTER
# ==================================================

def options_of(column):
    return sorted(df[column].astype(str).str.strip().unique().tolist())


with filters_box:
    f1, f2, f3, f4, f5 = st.columns([2.2, 1, 1, 1, 1])

search = f1.text_input(
    "Cari pengadaan",
    placeholder="Ketik nama pengadaan..."
)

tipe_filter = f2.multiselect(
    "Tipe",
    options_of("Tipe"),
    placeholder="Pilih Tipe..."
)

pic_filter = f3.multiselect(
    "PIC",
    options_of("PIC"),
    placeholder="Pilih PIC..."
)

vendor_filter = f4.multiselect(
    "Vendor",
    options_of("Vendor"),
    placeholder="Pilih Vendor..."
)

status_filter = f5.selectbox(
    "Status Pengadaan",
    ["Semua"] + STATUS_ORDER
)

fdf = df.copy()

if search.strip():
    fdf = fdf[
        fdf["Nama Pengadaan"].str.contains(
            search.strip(), case=False, na=False, regex=False
        )
    ]

if tipe_filter:
    fdf = fdf[fdf["Tipe"].isin(tipe_filter)]

if pic_filter:
    fdf = fdf[fdf["PIC"].isin(pic_filter)]

if vendor_filter:
    fdf = fdf[fdf["Vendor"].isin(vendor_filter)]

if status_filter != "Semua":
    fdf = fdf[fdf["Status Pengadaan"] == status_filter]

fdf = fdf.reset_index(drop=True)

if fdf.empty:

    st.info("Tidak ada pengadaan yang cocok dengan filter saat ini.")

    st.stop()



total = len(fdf)
total_docs = total * len(DOCS)
avg_progress = fdf["Progress (%)"].mean()

docs_selesai = int(fdf["Done"].sum())
docs_berjalan = int(fdf["On Progress"].sum())
docs_belum = int(fdf["Pending"].sum())

proc_selesai = int((fdf["Status Pengadaan"] == "Selesai").sum())
proc_berjalan = int((fdf["Status Pengadaan"] == "Berjalan").sum())
proc_belum = int((fdf["Status Pengadaan"] == "Belum Mulai").sum())

with kpi_box:
    k1, k2, k3, k4, k5 = st.columns(5)

k1.markdown(
    kpi_card(
        "Total Pengadaan",
        total,
        "{} dokumen ({} per pengadaan)".format(total_docs, len(DOCS)),
        BRAND_PRIMARY,
        icon="file"
    ),
    unsafe_allow_html=True
)

k2.markdown(
    kpi_card(
        "Selesai",
        proc_selesai,
        "{} Dokumen Selesai {}/{}".format(
            docs_selesai, len(DOCS), len(DOCS)
        ),
        BRAND_PRIMARY,
        icon="check"
    ),
    unsafe_allow_html=True
)
k3.markdown(
    kpi_card(
        "Berjalan",
        proc_berjalan,
        "{} Dokumen Berjalan".format(docs_berjalan),
        BRAND_PRIMARY,
        icon="clock"
    ),
    unsafe_allow_html=True
)
k4.markdown(
    kpi_card(
        "Belum Mulai",
        proc_belum,
        "{} Dokumen Belum Mulai".format(docs_belum),
        BRAND_PRIMARY,
        icon="list"
    ),
    unsafe_allow_html=True
)
k5.markdown(
    kpi_card(
        "Rata-rata Progres",
        "{:.1f}%".format(avg_progress),
        "hijau + ½ kuning",
        BRAND_PRIMARY,
        icon="pie"
    ),
    unsafe_allow_html=True
)


# Warna grafik (nama tampilan -> warna). Dipakai di menu Ringkasan & Detail.
label_colors = {
    DOC_STATUS_LABEL[key]: COLORS[key] for key in COLORS
}


# --------------------------------------------------
# MENU 1: RINGKASAN
# --------------------------------------------------

if menu == MENU_SUMMARY:

    # ---------- 1) Daftar Pengadaan (tabel) ----------

    st.markdown(
        '<div class="section-title">Daftar Pengadaan</div>',
        unsafe_allow_html=True
    )

    st.markdown(procurement_table_html(fdf), unsafe_allow_html=True)

    # ---------- Keterangan kelengkapan dokumen ----------

    st.markdown(document_legend_html(), unsafe_allow_html=True)

    # ---------- 2) Status Dokumen per Jenis Dokumen (grafik) ----------

    st.markdown(
        '<div class="section-title" style="margin-top:2rem;">'
        'Status Dokumen per Jenis Dokumen</div>',
        unsafe_allow_html=True
    )

   
    doc_labels = [
        wrap_label("{}. {}".format(number, doc))
        for number, doc in enumerate(DOCS, start=1)
    ]

    chart_rows = []

    for label, doc in zip(doc_labels, DOCS):
        for status in ["Done", "On Progress", "Pending"]:
            chart_rows.append({
                "Dokumen": label,
                "Status": DOC_STATUS_LABEL[status],
                "Jumlah": int((fdf[doc] == status).sum())
            })

    chart_df = pd.DataFrame(chart_rows)

    fig_bar = px.bar(
        chart_df,
        x="Jumlah",
        y="Dokumen",
        color="Status",
        orientation="h",
        barmode="stack",
        color_discrete_map=label_colors,
        category_orders={
            "Status": [
                DOC_STATUS_LABEL["Done"],
                DOC_STATUS_LABEL["On Progress"],
                DOC_STATUS_LABEL["Pending"],
            ]
        }
    )

   
    fig_bar.update_layout(
        height=560,
        font=dict(family=PLOT_FONT, color=BRAND_TEXT, size=13),
        margin=dict(l=24, r=32, t=64, b=32),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            xanchor="left",
            x=0,
            title_text="",
            font=dict(family=PLOT_FONT, color=BRAND_TEXT, size=13),
            entrywidth=130,
            entrywidthmode="pixels"
        ),
        xaxis_title=None,
        yaxis_title=None,
        bargap=0.28,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)"
    )

    fig_bar.update_yaxes(
        autorange="reversed",
        automargin=True,
        ticksuffix="  ",
        tickfont=dict(family=PLOT_FONT, color=BRAND_TEXT, size=13),
        showline=True,
        linecolor="rgba(15,36,71,0.25)"
    )

    x_axis_options = dict(
        showgrid=True,
        gridcolor="rgba(15,36,71,0.08)",
        automargin=True,
        rangemode="tozero",
        tickformat="d",
        tickfont=dict(family=PLOT_FONT, color=BRAND_TEXT, size=12)
    )

    # Bila jumlah pengadaan sedikit, tampilkan tiap angka bulat
    if total <= 10:
        x_axis_options["dtick"] = 1

    fig_bar.update_xaxes(**x_axis_options)

    # Wadah ber-key supaya di HP grafik bisa digeser horizontal (CSS
    # .st-key-chart_docs di blok RESPONSIF).
    with keyed_container("chart_docs"):
        show_chart(fig_bar)


# --------------------------------------------------
# MENU 2: DETAIL PENGADAAN
# --------------------------------------------------

elif menu == MENU_DETAIL:

    labels = [
        "{}. {}".format(int(r["No"]), r["Nama Pengadaan"])
        for _, r in fdf.iterrows()
    ]

    selected_label = st.selectbox(
        "Pilih pengadaan",
        labels,
        index=None,
        placeholder="Pilih pengadaan untuk melihat detail..."
    )

    if not selected_label:

        st.info(
            "Pilih salah satu pengadaan di atas untuk melihat "
            "detail dan kelengkapan dokumennya."
        )

    else:

        row = fdf.iloc[labels.index(selected_label)]

        tgl_tor = as_date(row["Tgl TOR"])
        tgl_request = as_date(row["Tgl Request"])
        tgl_selesai = as_date(row["Tgl Selesai"])

        progress_value = float(row["Progress (%)"])

        st.markdown(
            '<div class="section-title" style="margin-top:0.6rem;">{}</div>'.format(
                esc(row["Nama Pengadaan"])
            ),
            unsafe_allow_html=True
        )

        # ---------- Info umum ----------

        i1, i2, i3 = st.columns(3)

        i1.markdown(
            info_card("Tipe", row["Tipe"], "tag", BRAND_PRIMARY),
            unsafe_allow_html=True
        )
        i2.markdown(
            info_card("PIC", row["PIC"], "user", BRAND_PRIMARY),
            unsafe_allow_html=True
        )
        i3.markdown(
            info_card("Vendor", row["Vendor"], "building", BRAND_PRIMARY),
            unsafe_allow_html=True
        )

        st.write("")

        # ---------- Info tanggal ----------

        t1, t2, t3 = st.columns(3)

        t1.markdown(
            info_card(
                "Tanggal TOR Diterima", fmt_date(tgl_tor),
                "calendar", BRAND_PRIMARY
            ),
            unsafe_allow_html=True
        )
        t2.markdown(
            info_card(
                "Tanggal Request Pengadaan", fmt_date(tgl_request),
                "calendar", BRAND_PRIMARY
            ),
            unsafe_allow_html=True
        )
        t3.markdown(
            info_card(
                "Tanggal Pengadaan Selesai",
                fmt_date(tgl_selesai) if tgl_selesai else "Belum diisi",
                "check",
                BRAND_PRIMARY
            ),
            unsafe_allow_html=True
        )

        st.write("")

        # ---------- Waiting time ----------

        wt_tor_value, wt_tor_sub = waiting_info(tgl_tor, tgl_selesai, TODAY)
        wt_req_value, wt_req_sub = waiting_info(
            tgl_request, tgl_selesai, TODAY
        )

        w1, w2 = st.columns(2)

        w1.markdown(
            kpi_wide_card(
                "Waiting Time TOR", wt_tor_value, wt_tor_sub,
                BRAND_PRIMARY, "hourglass"
            ),
            unsafe_allow_html=True
        )
        w2.markdown(
            kpi_wide_card(
                "Waiting Time Pengadaan", wt_req_value, wt_req_sub,
                BRAND_PRIMARY, "timer"
            ),
            unsafe_allow_html=True
        )

        st.write("")

        # ---------- Progress bar ----------

        st.markdown(
            '<div class="pbar-head">'
            '<span>Progres Pengadaan</span><span>{:.1f}%</span></div>'
            '<div class="pbar"><div style="width:{:.1f}%;"></div></div>'.format(
                progress_value,
                min(max(progress_value, 0), 100)
            ),
            unsafe_allow_html=True
        )

        st.write("")

        # ---------- KPI dokumen ----------

        d1, d2, d3, d4 = st.columns(4)

        d1.markdown(
            kpi_card(
                "Selesai",
                int(row["Done"]),
                "dokumen hijau",
                BRAND_PRIMARY,
                icon="check"
            ),
            unsafe_allow_html=True
        )
        d2.markdown(
            kpi_card(
                "Berjalan",
                int(row["On Progress"]),
                "dokumen kuning",
                BRAND_PRIMARY,
                icon="clock"
            ),
            unsafe_allow_html=True
        )
        d3.markdown(
            kpi_card(
                "Belum Mulai",
                int(row["Pending"]),
                "dokumen putih",
                BRAND_PRIMARY,
                icon="list"
            ),
            unsafe_allow_html=True
        )
        d4.markdown(
            kpi_card(
                "Status Pengadaan",
                row["Status Pengadaan"],
                "progres {:.1f}%".format(progress_value),
                BRAND_PRIMARY,
                icon="bars"
            ),
            unsafe_allow_html=True
        )

        # ---------- Pemeriksaan konsistensi data ----------

        is_complete = row["Status Pengadaan"] == "Selesai"

        if tgl_selesai is not None and not is_complete:
            st.warning(
                "Kolom 'Pengadaan Selesai' sudah terisi, tetapi dokumen "
                "belum lengkap ({} dari {} hijau).".format(
                    int(row["Done"]), len(DOCS)
                )
            )
        elif tgl_selesai is None and is_complete:
            st.info(
                "Semua dokumen sudah hijau, tetapi kolom 'Pengadaan Selesai' "
                "belum diisi. Waiting time masih dihitung sampai hari ini."
            )

        st.write("")

        # ---------- Diagram + daftar dokumen ----------

        left, right = st.columns([1, 2.2])

        with left:

            st.markdown(
                '<div class="section-title" style="margin-top:0;">'
                'Diagram Progres</div>',
                unsafe_allow_html=True
            )

            chart_data = pd.DataFrame({
                "Status": [
                    DOC_STATUS_LABEL["Done"],
                    DOC_STATUS_LABEL["On Progress"],
                    DOC_STATUS_LABEL["Pending"],
                ],
                "Jumlah": [
                    int(row["Done"]),
                    int(row["On Progress"]),
                    int(row["Pending"])
                ]
            })

            fig = px.pie(
                chart_data,
                names="Status",
                values="Jumlah",
                hole=0.62,
                color="Status",
                color_discrete_map=label_colors,
                category_orders={
                    "Status": [
                        DOC_STATUS_LABEL["Done"],
                        DOC_STATUS_LABEL["On Progress"],
                        DOC_STATUS_LABEL["Pending"],
                    ]
                }
            )

            fig.update_traces(
                textinfo="value",
                sort=False,
                marker=dict(line=dict(color="#FFFFFF", width=2))
            )

            # Margin bawah dibuat lega (b=72) agar legenda tidak terpotong.
            fig.update_layout(
                height=380,
                font=dict(family=PLOT_FONT, color=BRAND_TEXT),
                margin=dict(l=16, r=16, t=16, b=72),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.06,
                    xanchor="center",
                    x=0.5,
                    title_text=""
                ),
                annotations=[
                    dict(
                        text="<b>{:.0f}%</b>".format(progress_value),
                        x=0.5,
                        y=0.5,
                        font_size=26,
                        showarrow=False
                    )
                ],
                paper_bgcolor="rgba(0,0,0,0)"
            )

            show_chart(fig)

        with right:

            st.markdown(
                '<div class="section-title" style="margin-top:0;">'
                'Rincian Dokumen</div>',
                unsafe_allow_html=True
            )

            st.markdown(doc_cards_html(row), unsafe_allow_html=True)


# ==================================================
# KETERANGAN
# ==================================================

footer_caption()
