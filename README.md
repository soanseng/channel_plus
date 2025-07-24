# Channel Plus 音檔下載器 
一個現代化的 Python 實作，用於下載[國立教育廣播電台 Channel Plus](https://channelplus.ner.gov.tw/) 的語言學習音檔。

## 📖 專案簡介

國立教育廣播電台的 Channel Plus 平台提供了豐富的語言學習教材，包含日語、韓語、法語、西班牙語、德語、義大利語、越南語、泰語、印尼語、阿拉伯語及英語等多種語言課程，品質相當優秀。

雖然平台支援線上收聽，但內建播放器功能有限，無法快轉、調整播放速度或離線收聽。這個工具讓您可以下載音檔到本機，使用您慣用的播放器自由收聽，支援快轉、倍速播放等功能。

**非常推薦大家多多利用國立教育廣播電台的資源學習語言 - 這些都是我們納稅錢支持的優質教育內容！** 🇹🇼

## ✨ 功能特色

### 🆕 Python 版本增強功能
- **🧩 智慧預設值**: 只需提供課程網址，自動偵測課程名稱、總集數並建立資料夾
- **📚 課程教材下載**: 自動偵測並下載課程附帶的 PDF 講義等教材檔案
- **⚡ 高效能下載**: 使用異步並發技術，下載速度比原版快 3 倍
- **📊 即時進度條**: 美觀的進度顯示，包含下載速度和預估剩餘時間
- **🔍 預覽模式**: `--dry-run` 參數可預覽要下載的內容，不實際下載
- **✅ 網址驗證**: `--validate-only` 參數可檢查課程網址是否有效
- **📝 詳細記錄**: `--verbose` 參數提供詳細的操作記錄，方便除錯
- **🔄 自動重試**: 網路不穩時自動重試，採用指數退避演算法
- **⚙️ 彈性設定**: 可自訂並發數量、逾時時間、重試次數等參數

### 🔧 核心功能
- **專業品質**: 高品質的音檔下載和檔名處理
- **智慧分頁**: 自動處理分頁邏輯（每頁 10 集）
- **音檔完整性**: 保持原始檔名和音質
- **錯誤處理**: 強健的錯誤處理和復原機制

## 🚀 安裝說明

### 前置需求
- Python 3.12 或更新版本
- [uv](https://docs.astral.sh/uv/) 套件管理工具

### 安裝 uv (如果尚未安裝)
```bash
# macOS 和 Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip 安裝
pip install uv
```

### 安裝 Channel Plus 下載器
```bash
# 下載專案
git clone <repository-url>
cd channel_plus

# 安裝相依套件
uv sync

# 測試安裝是否成功
uv run channel-plus --help
```

## 📚 使用方法

### 基本用法
```bash
# 最簡化用法（使用智慧預設值）
uv run channel-plus --link <課程網址>

# 完整用法
uv run channel-plus --path <下載路徑> --link <課程網址> --start <起始集數> --final <結束集數>
```

### 實際範例
```bash
# 🆕 最簡化：自動下載整個課程到 ~/Downloads/<課程名稱>/
uv run channel-plus --link https://channelplus.ner.gov.tw/viewalllang/49
# → 自動建立資料夾：~/Downloads/生活日語二/
# → 自動下載第 1-260 集（全部集數）

# 指定特定集數範圍
uv run channel-plus --link https://channelplus.ner.gov.tw/viewalllang/390 --start 155 --final 160
# → 下載第 155-160 集到 ~/Downloads/Yinka生動活潑日語會話/

# 自訂下載路徑
uv run channel-plus --path ~/Documents/Japanese --link https://channelplus.ner.gov.tw/viewalllang/49

# 完整自訂
uv run channel-plus --path ~/Downloads/English --link https://channelplus.ner.gov.tw/viewalllang/123 --start 1 --final 10 --concurrent 5
```

### 🧩 智慧預設值功能

**只需一個網址，輕鬆下載整個課程！**

系統會自動：
- 🔍 **偵測課程名稱**：從課程內容自動提取課程標題作為資料夾名稱
- 📊 **偵測總集數**：掃描所有分頁，自動找出最後一集
- 📁 **建立資料夾**：在 `~/Downloads/` 下以課程名稱建立專用資料夾
- 🎯 **設定範圍**：預設下載第 1 集到最後一集

```bash
# 只需提供網址，其他全部自動處理
uv run channel-plus --link https://channelplus.ner.gov.tw/viewalllang/49

# 系統會自動：
# - 偵測課程名稱：「生活日語二」
# - 偵測總集數：260 集
# - 建立路徑：~/Downloads/生活日語二/
# - 下載範圍：第 1-260 集
```

### 📚 課程教材自動下載功能

**全新功能：智慧偵測課程講義和學習資料！**

系統會自動：
- 🔍 **全面偵測**: 掃描所有要下載的集數，檢查每一集是否有附帶的學習資料
- 📥 **並行下載**: 與音檔同時下載教材，提升整體效率
- 📝 **保持原名**: 保留原始檔名，自動加上集數前綴以便整理
- 🎯 **智慧判斷**: 沒有教材的課程會顯示「無教材」，不會產生錯誤
- ⚡ **高效處理**: 使用並發下載，最多同時處理 3 個教材檔案

```bash
# 範例 1：課程 49 有一個 PDF 講義（整個課程共用）
uv run channel-plus --link https://channelplus.ner.gov.tw/viewalllang/49 --start 1 --final 2 --dry-run

# 輸出：
# 📚 Checking for course materials across all episodes...
# ✅ Found 1 course materials across 1 episodes
# Course materials found:
#   Ep01: 99長青天地生活日語講義(2).pdf

# 範例 2：課程 573 每一集都有專屬的 PDF 講義
uv run channel-plus --link https://channelplus.ner.gov.tw/viewalllang/573 --start 1 --final 3 --dry-run

# 輸出：
# 📚 Checking for course materials across all episodes...
# ✅ Found 3 course materials across 3 episodes
# Course materials found:
#   Ep01: 01 東方美人茶.pdf
#   Ep02: 02 台灣茶和日本茶_來賓今泉老師.pdf
#   Ep03: 03 P64 故宮博物院的有趣傳說.pdf

# 下載後的檔案結構：
# ~/Downloads/跟著Yinka走台灣/
# ├── course_materials/
# │   ├── 01 東方美人茶.pdf
# │   ├── 02 台灣茶和日本茶_來賓今泉老師.pdf
# │   └── 03 P64 故宮博物院的有趣傳說.pdf
# ├── 10001跟著Yinka走台灣.mp3
# ├── 10002跟著Yinka走台灣.mp3
# └── 10003跟著Yinka走台灣.mp3
```

### 進階功能

#### 🔍 預覽模式（不實際下載）
```bash
uv run channel-plus --path ~/Downloads --link https://channelplus.ner.gov.tw/viewalllang/390 --start 1 --final 5 --dry-run --verbose
```

#### ✅ 驗證課程網址
```bash
uv run channel-plus --path /tmp --link https://channelplus.ner.gov.tw/viewalllang/390 --start 1 --final 1 --validate-only
```

#### 📝 詳細記錄模式
```bash
uv run channel-plus --path ~/Downloads --link https://channelplus.ner.gov.tw/viewalllang/390 --start 1 --final 10 --verbose
```

#### ⚙️ 自訂下載參數
```bash
uv run channel-plus \
  --path ~/Downloads \
  --link https://channelplus.ner.gov.tw/viewalllang/390 \
  --start 1 --final 20 \
  --concurrent 8 \
  --timeout 600 \
  --retry-attempts 5 \
  --delay 0.5
```

## 📋 參數說明

| 參數 | 必填 | 說明 | 預設值 |
|------|------|------|--------|
| `--path` | ❌ | 音檔下載路徑 | `~/Downloads/<課程名稱>/` |
| `--link` | ✅ | Channel Plus 課程頁面網址 | - |
| `--start` | ❌ | 起始集數 | `1` |
| `--final` | ❌ | 結束集數 | 自動偵測最後一集 |
| `--concurrent` | ❌ | 並發下載數量 (1-10) | 3 |
| `--timeout` | ❌ | 請求逾時秒數 | 300 |
| `--retry-attempts` | ❌ | 重試次數 (1-10) | 3 |
| `--delay` | ❌ | 請求間隔秒數 | 1.0 |
| `--verbose` | ❌ | 顯示詳細記錄 | 關閉 |
| `--dry-run` | ❌ | 預覽模式（不實際下載） | 關閉 |
| `--validate-only` | ❌ | 僅驗證網址有效性 | 關閉 |

## 🎯 如何找到課程網址

1. 前往 [Channel Plus 官網](https://channelplus.ner.gov.tw/)
2. 選擇您想學習的語言分類
3. 點選特定課程進入課程頁面
4. 複製瀏覽器網址列的 URL，例如：
   - 日語：`https://channelplus.ner.gov.tw/viewalllang/390`
   - 英語：`https://channelplus.ner.gov.tw/viewalllang/123`
   - 法語：`https://channelplus.ner.gov.tw/viewalllang/456`

## 🔧 疑難排解

### 常見問題

**Q: 下載失敗或中斷怎麼辦？**
A: 程式具備自動重試功能。您也可以：
- 增加重試次數：`--retry-attempts 5`
- 增加逾時時間：`--timeout 600`
- 降低並發數量：`--concurrent 2`

**Q: 如何確認課程網址是否正確？**
A: 使用驗證模式：
```bash
uv run channel-plus --validate-only --path /tmp --link <課程網址> --start 1 --final 1
```

**Q: 下載速度太慢或太快被伺服器限制？**
A: 調整下載參數：
```bash
# 較保守的設定（適合網路不穩定時）
--concurrent 2 --delay 2.0

# 較積極的設定（適合網路狀況良好時）
--concurrent 6 --delay 0.5
```

**Q: 程式顯示找不到集數？**
A: 請檢查：
- 集數範圍是否正確（課程頁面會顯示總集數）
- 網址是否正確
- 使用 `--verbose` 查看詳細記錄

### 錯誤代碼說明

- **HTTP 401**: 伺服器拒絕存取，通常是暫時性問題，請稍後重試
- **HTTP 404**: 找不到指定的集數或課程
- **HTTP 429**: 請求過於頻繁，請降低並發數量或增加延遲時間
- **TimeoutError**: 網路逾時，請增加 `--timeout` 參數

## 🛠️ 開發說明

### 專案架構
```
src/channel_plus/
├── core/
│   ├── models.py      # 資料模型
│   ├── scraper.py     # 網頁爬蟲
│   ├── downloader.py  # 下載引擎
│   └── config.py      # 設定管理
├── utils/
│   └── http_client.py # HTTP 用戶端
└── main.py           # 主程式進入點
```

### 執行測試
```bash
# 執行所有測試
uv run pytest

# 執行特定測試
uv run pytest tests/test_models.py

# 執行整合測試（會連接真實網站）
uv run pytest tests/test_integration.py -m integration
```

### 開發模式安裝
```bash
# 安裝開發相依套件
uv sync --dev

# 程式碼格式化
uv run black src/ tests/

# 型別檢查
uv run mypy src/
```

## 📜 授權條款

請合理使用，尊重國立教育廣播電台的智慧財產權。

## 🙏 致謝

- 感謝國立教育廣播電台提供優質的語言學習資源
- 本 Python 版本使用現代化技術重新實作，提供更好的使用體驗

## 📞 回饋與建議

如果您在使用過程中遇到問題或有改善建議，歡迎透過以下方式聯繫：
- 建立 Issue 回報問題
- 提交 Pull Request 貢獻程式碼
- 分享使用心得和建議

---

**讓我們一起善用國立教育廣播電台的優質資源，提升語言學習效率！** 🚀📚