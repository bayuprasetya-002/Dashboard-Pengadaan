import base64
import colorsys
import html
import inspect
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

# Cek library pihak ketiga. Bila ada yang belum terpasang di Python yang
# sedang menjalankan Streamlit, tampilkan perintah install yang tepat
# (memakai Python yang sama dengan yang menjalankan aplikasi ini).
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

# Font grafik (disamakan dengan font Streamlit)
PLOT_FONT = "Source Sans, Source Sans Pro, Source Sans 3, sans-serif"

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
       besar / kecil. */
    --logo-height: 64px;

    /* Posisi tombol Refresh di sebelah kanan tab.
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

/* ---------- Tombol Refresh (sejajar dengan tab, di kanan) ----------
   Wadah tombol dibuat selebar penuh dan setinggi 0, lalu tombolnya
   diposisikan absolut di sisi KANAN baris tab. Lebar penuh wajib agar
   "right: 0" menempel ke tepi kanan halaman (bukan ke tepi kiri).
   Ukuran disamakan dengan tab (tinggi 40px, padding 0 16px, pil). */
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

/* ---------- Kotak peringatan ---------- */
.stApp [data-testid="stAlert"] {
    border-radius: 12px;
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
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
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
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
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

    st.plotly_chart(fig, **kwargs)


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

    # ----------------------------------------------
    # HITUNG JUMLAH DOKUMEN PER STATUS (dari warna dokumen 1-12)
    #
    #   Done        : jumlah dokumen berwarna hijau  -> "Selesai"
    #   On Progress : jumlah dokumen berwarna kuning -> "Berjalan"
    #   Pending     : jumlah dokumen berwarna putih  -> "Belum Mulai"
    # ----------------------------------------------

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


def progress_cell(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0

    width = min(max(number, 0.0), 100.0)

    return (
        '<td class="c-prog">'
        '<div class="pg-wrap">'
        '<div class="pg-bar"><div style="width:{width:.1f}%;"></div></div>'
        '<span class="pg-text">{number:.1f}%</span>'
        '</div>'
        '</td>'
    ).format(width=width, number=number)


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


def refresh_data():
    """Hapus cache data lalu muat ulang halaman."""
    st.cache_data.clear()
    st.rerun()


# ==================================================
# HEADER
# Logo BRI (kiri) | judul + keterangan (tengah) | logo DWI (kanan).
# Tombol Refresh Data berada di sebelah kanan baris tab (lihat bagian
# TOMBOL REFRESH + TAB di bawah).
# ==================================================

st.markdown(
    header_html(datetime.now(WIB).strftime("%d %b %Y, %H:%M")),
    unsafe_allow_html=True
)


# ==================================================
# MEMUAT DATA
# ==================================================

try:

    df, info = load_data()

except Exception as error:

    st.error(
        "Gagal membaca Google Sheets. "
        "Periksa koneksi dan konfigurasi."
    )

    st.code(str(error))

    # Tombol cadangan agar tetap bisa memuat ulang saat terjadi error
    if st.button("🔄 Refresh Data", key="refresh_fallback"):
        refresh_data()

    st.stop()


if df.empty:

    st.warning("Data pengadaan belum tersedia.")

    if st.button("🔄 Refresh Data", key="refresh_fallback"):
        refresh_data()

    st.stop()


if info.get("number_row_sheet") is None:

    st.warning(
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
    st.warning(
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

    if st.button("🔄 Refresh Data", key="refresh_fallback"):
        refresh_data()

    st.stop()


# ==================================================
# KARTU KPI
#
# Kartu Selesai / Berjalan / Belum Mulai dihitung PER DOKUMEN:
#   hijau  = Selesai
#   kuning = Berjalan
#   putih  = Belum Mulai
# Sebuah pengadaan baru dihitung "Selesai" bila 12 dokumennya hijau semua
# (angkanya ditampilkan di baris keterangan tiap kartu).
#
# Semua kartu KPI memakai aksen biru Qlola (BRAND_PRIMARY) agar seragam.
# ==================================================

total = len(fdf)
total_docs = total * len(DOCS)
avg_progress = fdf["Progress (%)"].mean()

docs_selesai = int(fdf["Done"].sum())
docs_berjalan = int(fdf["On Progress"].sum())
docs_belum = int(fdf["Pending"].sum())

proc_selesai = int((fdf["Status Pengadaan"] == "Selesai").sum())
proc_berjalan = int((fdf["Status Pengadaan"] == "Berjalan").sum())
proc_belum = int((fdf["Status Pengadaan"] == "Belum Mulai").sum())

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


# ==================================================
# TOMBOL REFRESH + TAB
#
# Tombol dirender tepat sebelum tab. Lewat CSS (.st-key-refresh_btn)
# wadah tombol dibuat selebar penuh & setinggi 0, lalu tombolnya
# diposisikan di sisi KANAN baris tab dengan ukuran yang sama seperti
# tab (tinggi 40px, bentuk pil).
# Bila posisinya kurang pas secara vertikal, ubah nilai --refresh-top
# di blok :root pada CSS.
# ==================================================

if st.button("🔄 Refresh Data", key="refresh_btn"):
    refresh_data()

tab_summary, tab_detail = st.tabs(
    ["📋 Ringkasan", "🔍 Detail Pengadaan"]
)

# Warna grafik (nama tampilan -> warna). Dipakai di tab Ringkasan & Detail.
label_colors = {
    DOC_STATUS_LABEL[key]: COLORS[key] for key in COLORS
}


# --------------------------------------------------
# TAB 1: RINGKASAN
# --------------------------------------------------

with tab_summary:

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

    chart_rows = []

    for number, doc in enumerate(DOCS, start=1):
        for status in ["Done", "On Progress", "Pending"]:
            chart_rows.append({
                "Dokumen": "{}. {}".format(number, short_label(doc)),
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

    # Margin atas diberi ruang untuk legenda; margin lain sebagai
    # "padding" kartu putih (padding CSS kartu = 0).
    fig_bar.update_layout(
        height=480,
        font=dict(family=PLOT_FONT, color=BRAND_TEXT),
        margin=dict(l=16, r=20, t=56, b=16),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            xanchor="left",
            x=0,
            title_text=""
        ),
        xaxis_title=None,
        yaxis_title=None,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    fig_bar.update_yaxes(autorange="reversed")
    fig_bar.update_xaxes(showgrid=True, gridcolor="rgba(15,36,71,0.08)")

    show_chart(fig_bar)


# --------------------------------------------------
# TAB 2: DETAIL PENGADAAN
# --------------------------------------------------

with tab_detail:

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

st.write("")

st.caption(
    "Keterangan warna sel di Google Sheets:  "
    "🟩 Hijau = Selesai   |   🟨 Kuning = Berjalan   |   ⬜ Putih = Belum Mulai"
)
