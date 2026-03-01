"""
PDF Chapter Splitter — A Streamlit Web Application
===================================================
Upload a PDF book, detect chapters automatically (via bookmarks, regex, or
manual entry), preview them, split into individual PDFs, and download as ZIP.
"""

import io
import os
import re
import shutil
import tempfile
import time
import zipfile
from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd
import streamlit as st
from pypdf import PdfReader, PdfWriter

# ──────────────────────────── Page config ────────────────────────────────────
st.set_page_config(
    page_title="PDF Chapter Splitter",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── Custom CSS ─────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global ─────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Header banner ─────────────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.8rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, .35);
    }
    .main-header h1 { margin: 0; font-size: 2.2rem; font-weight: 700; }
    .main-header p  { margin: .4rem 0 0; opacity: .88; font-size: 1.05rem; }

    /* ── Stat cards ─────────────────────────────────── */
    .stat-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.2rem 1.4rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,.08);
        transition: transform .2s;
    }
    .stat-card:hover { transform: translateY(-3px); }
    .stat-card .value { font-size: 1.8rem; font-weight: 700; color: #667eea; }
    .stat-card .label { font-size: .85rem; color: #555; margin-top: .25rem; }

    /* ── Selection toolbar ──────────────────────────── */
    .sel-toolbar {
        display: flex; gap: .6rem; flex-wrap: wrap;
        align-items: center;
        margin-bottom: 1rem;
    }
    .sel-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: #fff;
        padding: .25rem .75rem;
        border-radius: 20px;
        font-size: .82rem;
        font-weight: 600;
    }
    .sel-badge.muted {
        background: linear-gradient(135deg, #94a3b8, #64748b);
    }

    /* ── Sub-section list inside expander ───────────── */
    .sub-list { margin: .5rem 0 0 .2rem; padding: 0; }
    .sub-list li {
        list-style: none;
        padding: .3rem .6rem;
        margin-bottom: .25rem;
        border-left: 3px solid #c4b5fd;
        font-size: .88rem;
        color: #444;
        background: #faf5ff;
        border-radius: 0 6px 6px 0;
    }
    .sub-list li span.pg { color: #888; font-size: .78rem; margin-left: .5rem; }

    /* ── Log area ──────────────────────────────────── */
    .log-area {
        background: #1e1e2e;
        color: #a6e3a1;
        font-family: 'Fira Code', 'Consolas', monospace;
        font-size: .82rem;
        padding: 1rem;
        border-radius: 10px;
        max-height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* ── Sidebar tweaks ────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d2b55 0%, #1e1e2e 100%);
    }
    section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stTextInput label { font-weight: 600; }

    /* ── Buttons ───────────────────────────────────── */
    .stDownloadButton > button, .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all .25s !important;
    }
    .stDownloadButton > button:hover, .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 14px rgba(102,126,234,.4) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────── Session state defaults ─────────────────────────
_defaults = {
    "chapters": [],
    "split_done": False,
    "zip_bytes": None,
    "individual_files": {},
    "logs": [],
    "pdf_bytes": None,
    "total_pages": 0,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def _log(msg: str):
    """Append a timestamped message to the session log list."""
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{ts}] {msg}")


def sanitize_filename(name: str) -> str:
    """Remove characters not safe for filenames."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip().replace(" ", "_")
    return name or "Untitled"


# ── Chapter-vs-other heuristics ──────────────────────────────────────────────

_CHAPTER_KEYWORDS = re.compile(
    r"(chapter|ch\.?\s*\d|unit|part\s+\d|module|lesson|appendix)",
    re.IGNORECASE,
)

_NON_CHAPTER_KEYWORDS = re.compile(
    r"^(cover|title\s*page|half\s*title|copyright|brief\s*contents?|contents?"
    r"|preface|foreword|acknowledge?ments?|introduction|glossary|index"
    r"|bibliography|references|about\s*the\s*author|dedication|epigraph)",
    re.IGNORECASE,
)


def is_chapter_entry(title: str) -> bool:
    """Heuristic: True when *title* looks like a real chapter / appendix."""
    t = title.strip()
    if _CHAPTER_KEYWORDS.search(t):
        return True
    if _NON_CHAPTER_KEYWORDS.match(t):
        return False
    return True


# ──────────── Detection helpers ──────────────────────────────────────────────

def detect_bookmarks(pdf_bytes: bytes) -> list[dict]:
    """Return **top-level** chapters with nested sub-sections.

    Each returned dict has:
        title, start, end, pages, children: list[{title, start, end, pages}]
    Sub-bookmarks (depth >= 1) are grouped under their parent depth-0 entry.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)

    outlines = reader.outline
    if not outlines:
        return []

    # Step 1: Flatten bookmark tree, keeping depth info
    flat: list[dict] = []

    def _flatten(items, depth=0):
        for item in items:
            if isinstance(item, list):
                _flatten(item, depth + 1)
            else:
                try:
                    page_num = reader.get_destination_page_number(item)
                    flat.append({
                        "title": str(item.title).strip(),
                        "start": page_num + 1,
                        "depth": depth,
                    })
                except Exception:
                    pass

    _flatten(outlines)
    _log(f"Bookmarks scan complete — {len(flat)} raw entries found.")

    if not flat:
        return []

    # Step 2: Group into top-level entries with children
    #   - Every depth-0 entry becomes a chapter
    #   - Subsequent depth>0 entries become children of the last depth-0
    chapters: list[dict] = []

    for entry in flat:
        if entry["depth"] == 0:
            chapters.append({
                "title": entry["title"],
                "start": entry["start"],
                "end": None,          # filled below
                "pages": 0,
                "children": [],
            })
        else:
            # attach to last depth-0 entry
            if chapters:
                chapters[-1]["children"].append({
                    "title": entry["title"],
                    "start": entry["start"],
                    "end": None,
                    "pages": 0,
                })

    # Step 3: Compute end pages for each top-level chapter
    for i, ch in enumerate(chapters):
        ch["end"] = chapters[i + 1]["start"] - 1 if i + 1 < len(chapters) else total
        ch["pages"] = ch["end"] - ch["start"] + 1

        # Compute end pages for children within this chapter
        kids = ch["children"]
        for j, kid in enumerate(kids):
            kid["end"] = kids[j + 1]["start"] - 1 if j + 1 < len(kids) else ch["end"]
            kid["pages"] = kid["end"] - kid["start"] + 1

    _log(f"Grouped into {len(chapters)} top-level entries.")
    return chapters


def detect_by_regex(pdf_bytes: bytes, pattern: str) -> list[dict]:
    """Scan every page with *pattern* and return chapter hits."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    chapters: list[dict] = []

    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        _log(f"❌ Invalid regex: {exc}")
        return []

    for i in range(total):
        text = doc[i].get_text("text")
        match = compiled.search(text[:500])
        if match:
            title = match.group(0).strip()
            chapters.append({"title": title, "start": i + 1, "children": []})
            _log(f'  ▸ Detected "{title}" on page {i + 1}')

    _log(f"Regex scan — {len(chapters)} chapters found across {total} pages.")

    for i, ch in enumerate(chapters):
        ch["end"] = chapters[i + 1]["start"] - 1 if i + 1 < len(chapters) else total
        ch["pages"] = ch["end"] - ch["start"] + 1

    doc.close()
    return chapters


def render_page_image(pdf_bytes: bytes, page_num: int, zoom: float = 1.5) -> bytes:
    """Return a PNG image of a single page (0-indexed)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(zoom, zoom)
    pix = doc[page_num].get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


# ──────────── Split & ZIP ────────────────────────────────────────────────────

def split_pdf(pdf_bytes: bytes, chapters: list[dict]) -> tuple[bytes, dict]:
    """Split *pdf_bytes* into one PDF per chapter.

    Returns (zip_bytes, {filename: file_bytes}).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    tmp_dir = tempfile.mkdtemp()
    individual: dict[str, bytes] = {}

    for idx, ch in enumerate(chapters, start=1):
        writer = PdfWriter()
        for p in range(ch["start"] - 1, ch["end"]):
            writer.add_page(reader.pages[p])

        fname = f"{idx:02d}_{sanitize_filename(ch['title'])}.pdf"
        fpath = os.path.join(tmp_dir, fname)
        with open(fpath, "wb") as f:
            writer.write(f)
        with open(fpath, "rb") as f:
            individual[fname] = f.read()

        _log(f"  ✅ Created {fname} ({ch['pages']} pages)")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, data in individual.items():
            zf.writestr(fname, data)
    zip_buf.seek(0)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    _log(f"📦 ZIP archive ready — {len(individual)} files.")
    return zip_buf.read(), individual


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    detection_mode = st.selectbox(
        "Detection Mode",
        ["📑 Bookmark Based", "🔍 Text Pattern (Regex)", "✏️ Manual"],
        help="Choose how chapters are detected.",
    )

    custom_regex = ""

    if detection_mode == "🔍 Text Pattern (Regex)":
        preset = st.selectbox(
            "Preset patterns",
            [
                "Custom",
                r"Chapter\s+\d+",
                r"CHAPTER\s+\d+",
                r"Unit\s+\d+",
                r"Chapter\s+[IVXLCDM]+",
                r"Part\s+\d+",
            ],
        )
        custom_regex = st.text_input(
            "Regex pattern",
            value="" if preset == "Custom" else preset,
            help="Python-flavour regex. The first match per page is used.",
        )

    st.markdown("---")
    st.markdown(
        "**Built with** [Streamlit](https://streamlit.io) &bull; "
        "[PyPDF](https://pypdf.readthedocs.io) &bull; "
        "[PyMuPDF](https://pymupdf.readthedocs.io) &bull; "
        "Made with ❤️ by [Muhammad Nouman Tariq](https://github.com/Nomantariq12)"
    )

# ═════════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ═════════════════════════════════════════════════════════════════════════════

st.markdown(
    '<div class="main-header">'
    "<h1>📖 PDF Chapter Splitter</h1>"
    "<p>Upload a PDF book and split it into individual chapter files instantly.</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Upload ───────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload your PDF book",
    type=["pdf"],
    help="Only .pdf files are accepted.",
)

if uploaded:
    pdf_bytes = uploaded.read()
    st.session_state.pdf_bytes = pdf_bytes

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    st.session_state.total_pages = total_pages
    file_size_mb = len(pdf_bytes) / (1024 * 1024)

    # Stat cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="stat-card"><div class="value">{uploaded.name}</div>'
            f'<div class="label">File Name</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="stat-card"><div class="value">{file_size_mb:.2f} MB</div>'
            f'<div class="label">File Size</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="stat-card"><div class="value">{total_pages}</div>'
            f'<div class="label">Total Pages</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Detection ────────────────────────────────────────────────────────────
    chapters: list[dict] = []

    if detection_mode == "📑 Bookmark Based":
        with st.spinner("Scanning bookmarks …"):
            _log("Starting bookmark-based detection …")
            chapters = detect_bookmarks(pdf_bytes)
            if not chapters:
                st.warning("⚠️ No bookmarks / outline found. Try Regex or Manual mode.")
                _log("⚠️ No bookmarks found.")

    elif detection_mode == "🔍 Text Pattern (Regex)":
        if custom_regex:
            with st.spinner("Scanning pages with regex …"):
                _log(f"Starting regex scan with pattern: {custom_regex}")
                chapters = detect_by_regex(pdf_bytes, custom_regex)
                if not chapters:
                    st.warning("⚠️ No chapters matched. Try a different pattern.")
                    _log("⚠️ No regex matches.")
        else:
            st.info("Enter a regex pattern in the sidebar to begin detection.")

    elif detection_mode == "✏️ Manual":
        st.subheader("Define chapters manually")
        default_df = pd.DataFrame({
            "Title": ["Chapter 1", "Chapter 2"],
            "Start Page": [1, 10],
            "End Page": [9, total_pages],
        })
        edited = st.data_editor(
            default_df, num_rows="dynamic", use_container_width=True,
            column_config={
                "Start Page": st.column_config.NumberColumn(min_value=1, max_value=total_pages),
                "End Page": st.column_config.NumberColumn(min_value=1, max_value=total_pages),
            },
        )
        valid = True
        for _, row in edited.iterrows():
            if not row["Title"] or pd.isna(row["Start Page"]) or pd.isna(row["End Page"]):
                valid = False
            elif int(row["Start Page"]) > int(row["End Page"]):
                valid = False
            elif int(row["End Page"]) > total_pages or int(row["Start Page"]) < 1:
                valid = False

        if valid and len(edited):
            chapters = []
            for _, row in edited.iterrows():
                s, e = int(row["Start Page"]), int(row["End Page"])
                chapters.append({
                    "title": str(row["Title"]),
                    "start": s, "end": e,
                    "pages": e - s + 1,
                    "children": [],
                })
            _log(f"Manual mode — {len(chapters)} chapters defined.")
        elif not valid:
            st.error("❌ Check your entries — titles must be non-empty and page "
                     "ranges valid (1 .. {}).".format(total_pages))

    st.session_state.chapters = chapters

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER SELECTION PANEL
    # ══════════════════════════════════════════════════════════════════════════
    if chapters:
        st.markdown("### 📋 Detected Chapters")

        total_entries = len(chapters)
        chapter_count = sum(1 for c in chapters if is_chapter_entry(c["title"]))
        other_count = total_entries - chapter_count

        st.markdown(
            f'<div class="sel-toolbar">'
            f'  <span class="sel-badge">{total_entries} total</span>'
            f'  <span class="sel-badge">{chapter_count} chapters</span>'
            f'  <span class="sel-badge muted">{other_count} other</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Bulk-action buttons ──────────────────────────────────────────
        btn_cols = st.columns(4)
        with btn_cols[0]:
            select_all = st.button("✅ Select All", use_container_width=True)
        with btn_cols[1]:
            deselect_all = st.button("⬜ Deselect All", use_container_width=True)
        with btn_cols[2]:
            select_chapters = st.button("📑 Chapters Only", use_container_width=True,
                                        help="Select only chapter & appendix entries")
        with btn_cols[3]:
            invert_sel = st.button("🔄 Invert", use_container_width=True)

        # ── Helper: set all checkbox widget keys at once ────────────────
        def _set_all(values: list[bool]):
            """Write directly to each checkbox's widget key so Streamlit
            picks up the new value on the next rerun."""
            for i, v in enumerate(values):
                st.session_state[f"chk_{i}"] = v

        # Init checkbox keys on first load / when chapter count changes
        if f"chk_0" not in st.session_state or (
            f"chk_{total_entries - 1}" not in st.session_state
        ):
            _set_all([is_chapter_entry(c["title"]) for c in chapters])

        # Apply bulk actions (write to widget keys, then rerun)
        if select_all:
            _set_all([True] * total_entries)
            st.rerun()
        if deselect_all:
            _set_all([False] * total_entries)
            st.rerun()
        if select_chapters:
            _set_all([is_chapter_entry(c["title"]) for c in chapters])
            st.rerun()
        if invert_sel:
            _set_all([not st.session_state.get(f"chk_{i}", False)
                      for i in range(total_entries)])
            st.rerun()

        st.markdown("---")

        # ── Per-chapter row: checkbox + expander with sub-sections ───────
        for idx, ch in enumerate(chapters):
            is_ch = is_chapter_entry(ch["title"])
            icon = "📄" if is_ch else "📎"
            n_kids = len(ch.get("children", []))
            sub_info = f"  •  {n_kids} sub-sections" if n_kids else ""
            label = (f"{icon}  {ch['title']}   ·  "
                     f"pp. {ch['start']}–{ch['end']}  "
                     f"({ch['pages']} pages){sub_info}")

            st.checkbox(label, key=f"chk_{idx}")

            # Expandable preview with first-page thumbnail & sub-sections
            with st.expander(f"Details — {ch['title']}", expanded=False):
                col_img, col_info = st.columns([1, 2])
                with col_img:
                    try:
                        img = render_page_image(pdf_bytes, ch["start"] - 1)
                        st.image(img, caption=f"Page {ch['start']}",
                                 use_container_width=True)
                    except Exception:
                        st.info("Preview not available.")
                with col_info:
                    st.markdown(f"**Title:** {ch['title']}")
                    st.markdown(f"**Pages:** {ch['start']} – {ch['end']}  "
                                f"({ch['pages']} pages)")

                    kids = ch.get("children", [])
                    if kids:
                        st.markdown(f"**Sub-sections ({len(kids)}):**")
                        li_items = "".join(
                            f'<li>{k["title"]}'
                            f'<span class="pg">pp. {k["start"]}–{k["end"]}</span>'
                            f'</li>'
                            for k in kids
                        )
                        st.markdown(
                            f'<ul class="sub-list">{li_items}</ul>',
                            unsafe_allow_html=True,
                        )

        # ── Summary + Split ──────────────────────────────────────────────
        selected_chapters = [
            ch for i, ch in enumerate(chapters)
            if st.session_state.get(f"chk_{i}", False)
        ]
        n_sel = len(selected_chapters)
        total_sel_pages = sum(c["pages"] for c in selected_chapters)

        st.markdown("---")
        st.markdown(
            f"**{n_sel}** of **{total_entries}** entries selected  "
            f"({total_sel_pages} pages total)."
        )

        if n_sel == 0:
            st.warning("Select at least one entry to split.")
        else:
            est_sec = max(1, n_sel * 0.5 + total_sel_pages * 0.01)
            st.caption(f"⏱ Estimated processing time: ~{est_sec:.0f}s")

            if st.button("✂️  Split Selected Chapters", type="primary",
                         use_container_width=True):
                _log(f"Splitting {n_sel} selected entries ({total_sel_pages} pages) …")
                progress = st.progress(0, text="Splitting …")
                start_time = time.time()

                zip_bytes, individual = split_pdf(pdf_bytes, selected_chapters)

                elapsed = time.time() - start_time
                progress.progress(100, text=f"Done in {elapsed:.1f}s ✅")

                st.session_state.zip_bytes = zip_bytes
                st.session_state.individual_files = individual
                st.session_state.split_done = True
                _log(f"Split complete — {n_sel} files in {elapsed:.1f}s.")
                st.rerun()

    # ── Downloads ────────────────────────────────────────────────────────────
    if st.session_state.split_done:
        st.markdown("### 📥 Download")

        st.download_button(
            label="⬇️  Download All Chapters (ZIP)",
            data=st.session_state.zip_bytes,
            file_name="chapters.zip",
            mime="application/zip",
            use_container_width=True,
        )

        with st.expander("Download individual chapters"):
            for fname, data in st.session_state.individual_files.items():
                st.download_button(
                    label=f"⬇️ {fname}",
                    data=data,
                    file_name=fname,
                    mime="application/pdf",
                    key=f"dl_{fname}",
                )

    # ── Log panel ────────────────────────────────────────────────────────────
    if st.session_state.logs:
        st.markdown("### 🪵 Processing Log")
        log_text = "\n".join(st.session_state.logs)
        st.markdown(f'<div class="log-area">{log_text}</div>',
                    unsafe_allow_html=True)

else:
    # landing state
    st.info("👆 Upload a PDF to get started.")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("#### 📑 Bookmark Mode\nAuto-detect chapters from the PDF outline.")
    with col_b:
        st.markdown("#### 🔍 Regex Mode\nFind chapters using text patterns like "
                     "*Chapter 1*, *Unit 3*, etc.")
    with col_c:
        st.markdown("#### ✏️ Manual Mode\nDefine your own chapters with custom page ranges.")
