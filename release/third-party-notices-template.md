# 第三方軟體授權聲明 — 媒體啟動器

> **使用說明**：填寫各套件的實際版本號後，將本檔案另存為 `third-party-notices.txt`，  
> 隨安裝包一起發佈。標記「TODO」的欄位請在發佈前確認。

---

## Python

**Version:** TODO（執行 `python --version` 取得建置時版本）  
**License:** Python Software Foundation License Version 2 (PSF-2.0)  
**Source:** https://www.python.org/  
**Notice:**  
Python and the Python logos are trademarks or registered trademarks of the Python Software Foundation.  
This product includes software developed by the Python Software Foundation.  
Full license text: https://docs.python.org/3/license.html

---

## PyInstaller

**Version:** TODO（執行 `.venv\Scripts\pyinstaller --version` 取得）  
**License:** GNU General Public License v2 or later (GPL-2.0-or-later), with Bootloader Exception  
**Source:** https://pyinstaller.org/  
**Notice:**  
PyInstaller is licensed under GPL v2+. The bootloader (embedded in the generated executable) is covered by the Bootloader Exception, which grants an exemption from the GPL for programs packaged with PyInstaller.  
This means the packaged application itself does not need to be GPL-licensed.  
Full license text: https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt

---

## Pillow

**Version:** TODO（執行 `python -c "import PIL; print(PIL.__version__)"` 取得）  
**License:** Historical Permission Notice and Disclaimer (HPND)  
**Source:** https://python-pillow.org/  
**Notice:**  
The Python Imaging Library (PIL) is

    Copyright © 1997-2011 by Secret Labs AB
    Copyright © 1995-2011 by Fredrik Lundh

Pillow is the friendly PIL fork. It is

    Copyright © 2010-present by Jeffrey A. Clark (Alex) and contributors.

Full license text: https://github.com/python-pillow/Pillow/blob/main/LICENSE

---

## PyMuPDF (fitz)

**Version:** TODO（執行 `python -c "import fitz; print(fitz.version[0])"` 取得）  
**License:** GNU Affero General Public License v3.0 (AGPL-3.0)  
**Source:** https://pymupdf.readthedocs.io/  
**Notice:**  
PyMuPDF is licensed under AGPL v3, and is used for rendering PDF thumbnails in this application.

> ⚠️ **授權注意事項（中文）**：
> AGPL v3 要求：若你透過網路（包含 localhost HTTP server）提供使用 AGPL 軟體的服務，
> 且使用者能與服務互動，則必須向使用者提供完整原始碼。
>
> **本應用程式現況**：
> - 媒體啟動器為 localhost 服務，僅限本機使用，不對外提供服務
> - 本專案原始碼為 `launcher.py` 單一檔案，若有需要可完整提供
> - 學校行政內部使用是否符合 AGPL 條款，建議發佈前由法律顧問確認
>
> **若無法接受 AGPL 授權**，可考慮：
> 1. 移除 PDF 縮圖功能（PDF 仍可瀏覽，只顯示 📄 圖示）
> 2. 向 Artifex（PyMuPDF 商業授權方）購買商業授權

Full license text: https://www.gnu.org/licenses/agpl-3.0.html  
PyMuPDF commercial license: https://pymupdf.readthedocs.io/en/latest/about.html

---

## ffmpeg（若發佈包含 tools/ffmpeg.exe）

**Version:** TODO（執行 `ffmpeg -version` 取得）  
**Build:** TODO（記錄來源，例如：gyan.dev ffmpeg-release-essentials）  
**License:** GNU General Public License v2 or later (GPL-2.0-or-later)  
（若使用 LGPL 版本請更新此欄位）  
**Source:** https://ffmpeg.org/  
**Notice:**  
FFmpeg is a trademark of Fabrice Bellard, originator of the FFmpeg project.  
FFmpeg is licensed under the GNU Lesser General Public License (LGPL) version 2.1 or later.  
However, FFmpeg incorporates several optional parts and optimizations that are covered by the GNU General Public License (GPL) version 2 or later.  
If you use a GPL-enabled build (e.g., builds that include libx264, libx265), the entire build is covered by GPL.

**Source code availability:**  
Pursuant to GPL requirements, the source code for the version of FFmpeg included in this package can be obtained from:  
- https://ffmpeg.org/download.html  
- Or from the build provider: TODO（填入來源 URL）

Full license text: https://ffmpeg.org/legal.html

> ⚠️ **若發佈包不含 ffmpeg**：請刪除本節，並附加說明：
> "ffmpeg is NOT included in this package. Video thumbnail generation is not available.
> Users may install ffmpeg separately to enable this feature."

---

## 授權聲明填寫 Checklist（發佈前確認）

發佈前請確認以下每一項：

- [ ] Python 版本號已填寫
- [ ] PyInstaller 版本號已填寫
- [ ] Pillow 版本號已填寫
- [ ] PyMuPDF 版本號已填寫
- [ ] PyMuPDF AGPL 授權影響已評估（學校用途、是否需商業授權）
- [ ] ffmpeg 版本號已填寫（若包含）
- [ ] ffmpeg 來源 URL 已填寫（若包含）
- [ ] ffmpeg 版本是 GPL 版還是 LGPL 版已確認
- [ ] 本聲明文件已更名為 `third-party-notices.txt`
- [ ] `third-party-notices.txt` 已放入發佈包

---

*此模板由媒體啟動器開發人員準備。版本號欄位需在每次發佈時人工確認並填寫。*
