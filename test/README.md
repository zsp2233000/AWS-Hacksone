# Locust 壓力測試使用指南

## 快速開始

### 1. 安裝依賴
已經為您安裝好 Locust，可以直接使用。

### 2. 基本使用方法

#### 方法一：使用 Web UI（推薦給初學者）
在 test 資料夾中打開終端機，執行：
```powershell
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws
```

然後在瀏覽器中打開 http://localhost:8089，您會看到 Locust 的 Web 介面。

#### 方法二：命令列模式（無 UI）
```powershell
# 輕量測試 (5個用戶，30秒)
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users 5 --spawn-rate 1 -t 30s --headless

# 中等測試 (20個用戶，60秒)
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users 20 --spawn-rate 2 -t 60s --headless

# 高負載測試 (50個用戶，120秒)
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users 50 --spawn-rate 5 -t 120s --headless

# 壓力測試 (100個用戶，180秒)
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users 100 --spawn-rate 10 -t 180s --headless
```

### 3. 參數說明

- `--users`: 最大併發用戶數
- `--spawn-rate`: 每秒產生的新用戶數
- `-t` 或 `--run-time`: 測試運行時間（如 30s, 2m, 1h）
- `--headless`: 無圖形介面模式
- `--host`: 目標伺服器地址

### 4. 測試場景說明

腳本包含三種測試場景：
1. **send_notification_batch**: 每次發送100筆通知資料（權重：1）
2. **send_notification_small_batch**: 每次發送10筆通知資料（權重：2）
3. **send_notification_single**: 每次發送1筆通知資料（權重：1）

權重表示任務被執行的相對頻率。

### 5. 資料格式

每筆測試資料都包含：
- `ap_id`: 固定為 "MID-LX-LNK-01"
- `transaction_id`: 隨機生成的12位字元ID
- `token`: 模擬的 FCM token
- `payload`: 包含通知標題、內容和連結

### 6. 輸出報告

測試完成後，Locust 會顯示：
- 總請求數
- 失敗請求數
- 回應時間統計（平均、最小、最大、百分位數）
- 每秒請求數（RPS）
- 錯誤統計

### 7. 建議的測試步驟

1. **先從輕量測試開始**：確保系統基本功能正常
2. **逐步增加負載**：觀察系統在不同負載下的表現
3. **記錄關鍵指標**：回應時間、成功率、錯誤率
4. **分析瓶頸**：找出系統性能的限制點

### 8. 監控要點

- 成功率應該保持在95%以上
- 平均回應時間應該在可接受範圍內
- 注意是否有錯誤或超時
- 觀察系統資源使用情況

## 進階使用

### 自定義測試資料量
如果要修改每次請求的資料筆數，可以編輯 `locustfile.py` 中的 `generate_test_data()` 函數的參數。

### 新增測試場景
可以在 `LoadTestUser` 類別中新增更多 `@task` 方法來創建不同的測試場景。

### 輸出結果到檔案
```powershell
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users 20 --spawn-rate 2 -t 60s --headless --html=report.html --csv=results
```

這會生成 HTML 報告和 CSV 資料檔案。
