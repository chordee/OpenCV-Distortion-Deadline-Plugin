# OpenCV Distortion Deadline Plugin

這是一個為 Thinkbox Deadline 設計的自定義插件，用於批次處理影像的畸變校正（Undistort）或反向扭曲（Distort）。它基於 OpenCV 和 NumPy，並讀取標準的相機校正 JSON 檔（例如來自 NeRF 工具鏈的 `transforms.json`）。

## 功能特色

*   **自動分發腳本**：處理核心邏輯 (`distortion.py`) 內嵌於 Plugin 中，無需手動在 Render Node 上同步腳本路徑。
*   **高效能批次處理**：支援 Deadline Chunk Size 機制。當一個 Task 包含多幀時，腳本只會載入一次 JSON 並預計算一次扭曲貼圖，大幅提升處理速度。
*   **雙向處理**：支援去畸變 (Undistort/Restore) 與 模擬畸變 (Distort/Reverse)。
*   **格式支援**：自動偵測並支援 EXR (保留浮點數精度) 及一般圖像格式 (JPG, PNG 等)。
*   **魚眼支援**：相容 OpenCV 的標準透視模型與魚眼模型。
*   **零部署環境 (uv)**：利用 `uv` 自動管理 Python 環境，Worker 無需預裝 Python 或 OpenCV 套件。

## 1. 安裝插件到 Deadline

要讓 Deadline 認識這個新插件，您需要將插件檔案複製到 Deadline Repository。

1.  找到您的 **Deadline Repository** 路徑（通常在檔案伺服器上，例如 `\\Server\DeadlineRepository10`）。
2.  進入 `custom\plugins` 資料夾。
3.  將本專案中的 `deadline_plugin\OpenCVDistortion` 資料夾完整複製過去。

安裝後的結構應該如下所示：
```text
\\Server\DeadlineRepository10\
  └── custom\
      └── plugins\
          └── OpenCVDistortion\
              ├── OpenCVDistortion.param
              ├── OpenCVDistortion.py
              ├── distortion.py     <-- 核心邏輯腳本
              ├── pyproject.toml    <-- 環境定義
              ├── uv.lock           <-- 鎖定版本
              ├── uv-windows\       <-- Windows 版 uv 執行檔
              └── uv-linux\         <-- Linux 版 uv 執行檔
```

> **注意**：如果您在 Deadline Monitor 中沒有看到此插件，可能需要重啟 Monitor 或使用 Tools -> "Synchronize Monitor Scripts"。

## 2. 環境配置與注意事項

本插件採用 `uv` 進行環境隔離與管理，大幅簡化了 Worker 端的配置。

### 零配置運作
插件已內建各平台的 `uv` 執行檔，當 Job 啟動時，`uv` 會根據 `pyproject.toml` 自動在 Worker 本機建立所需的虛擬環境。

### 共享資源配置 (加速)
為了避免每個 Worker 都重複下載 Python 與套件，本插件建議使用共享路徑作為快取。這些路徑現在可以在 **Deadline Monitor** 中統一配置，無需在每次提交時指定：

1.  開啟 **Deadline Monitor**。
2.  進入 **Tools** -> **Configure Plugins**。
3.  在列表中選擇 **OpenCVDistortion**。
4.  在 **UV Configuration** 區塊中設定以下路徑：
    *   `UV Cache Dir`: 套件快取路徑 (例如 `\\server\share\uv_cache` 或 `/mnt/share/uv_cache`)。
    *   `Python Install Dir`: Python 執行檔快取路徑 (例如 `\\server\share\python` 或 `/mnt/share/python`)。

支援針對 Windows 與 Linux 平台分別設定不同的路徑。

### 路徑對應 (Path Mapping) 支援
本插件已整合 Deadline 的 **Path Mapping** 功能。如果您在 Deadline Repository 中設定了 Windows 與 Linux/Mac 之間的路徑對應規則，插件會自動轉換 `JSON 路徑`、`輸入路徑` 與 `輸出路徑`。

## 3. 如何提交任務 (Submit Job)

本專案提供了一個 `submit_job.py` 命令行工具，讓您可以輕鬆提交任務並指定參數。

### 基本語法

```bash
python submit_job.py --input <InputPattern> --output <OutputDir> --json <JsonPath> --frames <Range> [Options]
```

### 參數說明

*   `--input`: 輸入檔案的路徑，使用 `####` 代表幀號。例如：`Z:/shots/seq01/plate.####.exr`
*   `--output`: 輸出資料夾。例如：`Z:/shots/seq01/undistorted`
*   `--json`: 相機參數 JSON 檔路徑。
*   `--frames`: 幀範圍。例如：`1001-1050`
*   `--distort`: 如果加上此標籤，將執行 **扭曲 (Distort)** 模式。預設為 **去畸變 (Undistort)**。
*   `--chunk-size`: 每個 Task 包含的幀數（預設 1）。建議設為 5~10 以利用批次處理優勢，減少重複初始化時間。

### 範例：提交去畸變任務

```bash
python submit_job.py ^
  --input "Z:\projects\MyMovie\shots\shot_01\plate_v01.####.exr" ^
  --output "Z:\projects\MyMovie\shots\shot_01\plate_undistorted" ^
  --json "Z:\projects\MyMovie\shots\shot_01\transforms.json" ^
  --frames "1001-1100" ^
  --job-name "Undistort Shot 01"
```

### 範例：提交反向扭曲任務

```bash
python submit_job.py ^
  --input "Z:\projects\MyMovie\shots\shot_01\cg_render.####.exr" ^
  --output "Z:\projects\MyMovie\shots\shot_01\cg_distorted" ^
  --json "Z:\projects\MyMovie\shots\shot_01\transforms.json" ^
  --frames "1001-1100" ^
  --distort ^
  --job-name "Distort CG Shot 01"
```

### GUI 提交工具 (GUI Submitter)

除了命令行工具，本專案也提供了一個圖形化介面，方便使用者操作。

**需求**：
*   需要安裝 `PySide2` 或 `PySide6` (通常 Maya/Houdini/Nuke 已內建)。

**獨立執行**：
```bash
pip install PySide6  # 如果尚未安裝
python submit_job_gui.py
```

**在 DCC 軟體中執行 (Maya/Houdini/Nuke)**：
您可以將此工具整合至 3D 軟體的架上工具 (Shelf Tool)。

```python
import sys

# 將工具路徑加入環境
plugin_path = r"D:\path\to\OpenCV-Distortion-Deadline-Plugin"
if plugin_path not in sys.path:
    sys.path.append(plugin_path)

import submit_job_gui
# 啟動 UI
submit_job_gui.show_ui()
```

## 4. 除錯 (Troubleshooting)

*   **UV 執行錯誤**:
    *   請確保 Render Node 可以存取在 Deadline Plugin Config 中設定的快取路徑。
    *   如果您更改了共享路徑，請記得到 **Tools -> Configure Plugins -> OpenCVDistortion** 進行更新。
*   **權限問題 (Linux)**:
    *   插件會嘗試自動對 `uv` 執行檔執行 `chmod +x`。如果失敗，請手動確認 Repository 中的 `uv-linux/uv` 具備執行權限。

## 開發者資訊

*   **Plugin 核心**： `deadline_plugin/OpenCVDistortion/OpenCVDistortion.py`
*   **處理邏輯**：該資料夾下的 `distortion.py`
*   **環境管理**： `pyproject.toml`, `uv.lock`
