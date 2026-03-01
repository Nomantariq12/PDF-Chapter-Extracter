# 📖 PDF Chapter Splitter

A desktop application to upload a PDF book, detect chapters automatically, preview them, and split into individual PDF files.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

- **📑 Bookmark Detection** — Auto-detect chapters from the PDF outline/bookmarks
- **🔍 Regex Detection** — Find chapters using text patterns (e.g. `Chapter \d+`)
- **✏️ Manual Mode** — Define custom chapters with page ranges
- **👀 Page Preview** — Thumbnail previews of chapter first pages
- **📦 Batch Download** — Download all chapters as a ZIP or individually
- **🖥️ Desktop App** — Runs in a native window (no browser needed)
- **📤 Shareable EXE** — Build a single `.exe` file to share with anyone

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Windows 10 (21H2+) or Windows 11

### Installation

```bash
# Clone or download this repo
git clone https://github.com/Nomantariq12/Pdf_chapter_extracter.git
cd Pdf_chapter_extracter

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run as Desktop App

```bash
python launcher.py
```

A native desktop window opens with the full app — no browser required.

### Run as Web App (alternative)

```bash
streamlit run app.py
```

Opens in your default browser at `http://localhost:8501`.

## 📦 Build Shareable EXE

Double-click **`build.bat`**, or run manually:

```bash
venv\Scripts\activate
python build.py
```

Output: `dist/PDFChapterSplitter.exe` — a single file you can send to anyone.

> **Note:** The EXE is ~150–300 MB (bundles Python + all dependencies). First launch takes ~5–15s to self-extract; subsequent launches are faster. Recipients don't need Python installed.

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| UI Framework | [Streamlit](https://streamlit.io) |
| PDF Reading | [PyPDF](https://pypdf.readthedocs.io) + [PyMuPDF](https://pymupdf.readthedocs.io) |
| Desktop Window | [PyWebView](https://pywebview.flowrl.com) |
| EXE Packaging | [PyInstaller](https://pyinstaller.org) |
| Data Handling | [Pandas](https://pandas.pydata.org) |

## 📁 Project Structure

```
Pdf_chapter_extracter/
├── app.py           # Streamlit application (main UI + logic)
├── launcher.py      # Desktop launcher (PyWebView wrapper)
├── build.py         # PyInstaller build script
├── build.bat        # One-click Windows build
├── requirements.txt # Python dependencies
└── LICENSE          # MIT License
```

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Muhammad Nouman Tariq** — [GitHub](https://github.com/Nomantariq12)