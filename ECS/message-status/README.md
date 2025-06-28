# Message Status Task

一個運行在 ECS 上的 Python 應用程式，用於處理 SQS 訊息狀態更新。

## 功能

- 輪詢兩個 SQS 佇列：`StatusUpdateQueue` 和 `DLQ`
- 處理狀態訊息並轉發到 `EventQueue`
- 優雅的錯誤處理和日誌記錄
- 支援批次處理和長輪詢
- Docker 化部署

## 訊息格式

### 輸入訊息格式 (StatusUpdateQueue & DLQ)
```json
{
  "snsMessageId": "60606a79-5778-5383-9293-0ab09d2aed1b",
  "deliveryStatus": "SUCCESS",
  "providerResponse": "{\n  \"name\": \"projects/test-2aadd/messages/0:1750059026450891%2adabfdf2adabfdf\"\n}\n",
  "timestamp": "2025-06-16 07:30:26.354"
}
```

### 輸出訊息格式 (EventQueue)
```json
{
  "messageId": "60606a79-5778-5383-9293-0ab09d2aed1b",
  "status": "SUCCESS",
  "response": "{\n  \"name\": \"projects/test-2aadd/messages/0:1750059026450891%2adabfdf2adabfdf\"\n}\n",
  "timestamp": "2025-06-16 07:30:26.354",
  "sourceQueue": "StatusUpdateQueue",
  "processedAt": "2025-06-20T02:15:30.123Z"
}
```

## 環境變數

| 變數名稱 | 描述 | 必需 | 預設值 |
|---------|------|------|--------|
| `STATUS_UPDATE_QUEUE_URL` | StatusUpdateQueue 的 SQS URL | ✅ | - |
| `DLQ_URL` | DLQ 的 SQS URL | ✅ | - |
| `EVENT_QUEUE_URL` | EventQueue 的 SQS URL | ✅ | - |
| `POLL_INTERVAL` | 輪詢間隔 (秒) | ❌ | 10 |
| `MAX_MESSAGES` | 一次處理的最大訊息數 | ❌ | 10 |
| `LOG_LEVEL` | 日誌級別 | ❌ | INFO |

## 本地開發

### 先決條件
- Docker 和 Docker Compose
- AWS CLI (已配置認證)
- PowerShell (Windows) 或 Bash (Linux/macOS)

### 設定環境變數
```powershell
# Windows PowerShell
$env:STATUS_UPDATE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/StatusUpdateQueue"
$env:DLQ_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/DLQ"
$env:EVENT_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/EventQueue"
```

```bash
# Linux/macOS
export STATUS_UPDATE_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/StatusUpdateQueue"
export DLQ_URL="https://sqs.us-east-1.amazonaws.com/123456789012/DLQ"
export EVENT_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/EventQueue"
```

### 運行應用程式
```powershell
# Windows
.\test-local.ps1 run

# 其他命令
.\test-local.ps1 build    # 建構映像
.\test-local.ps1 logs     # 查看日誌
.\test-local.ps1 stop     # 停止應用程式
.\test-local.ps1 clean    # 清理資源
```

```bash
# Linux/macOS
docker-compose up --build
```

## 部署到 AWS ECS

### 先決條件
- AWS CLI 已配置
- 適當的 IAM 權限
- ECS 叢集已創建
- VPC 和子網路已配置

### 部署步驟

1. **Windows 部署**
   ```powershell
   .\deploy.ps1 -AccountId "123456789012" -Region "us-east-1"
   ```

2. **Linux/macOS 部署**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh 123456789012 us-east-1
   ```

### 創建 ECS 服務
```bash
aws ecs create-service \
  --cluster default \
  --service-name message-status-service \
  --task-definition message-status \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxx],securityGroups=[sg-xxxxxxxx],assignPublicIp=ENABLED}" \
  --region us-east-1
```

## 必要的 IAM 權限

### ECS Task Role 權限
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:SendMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:StatusUpdateQueue",
        "arn:aws:sqs:*:*:DLQ",
        "arn:aws:sqs:*:*:EventQueue"
      ]
    }
  ]
}
```

### ECS Execution Role 權限
- `AmazonECSTaskExecutionRolePolicy` (AWS 管理的政策)

## 監控和日誌

- CloudWatch Logs: `/ecs/message-status`
- 健康檢查：每 30 秒檢查一次進程狀態
- 應用程式日誌包含詳細的處理狀態和錯誤信息

## 故障排除

### 常見問題

1. **AWS 認證錯誤**
   - 檢查 AWS credentials 配置
   - 確認 ECS Task Role 和 Execution Role 權限

2. **SQS 權限錯誤**
   - 驗證 IAM 權限設定
   - 檢查 SQS 佇列政策

3. **應用程式無法啟動**
   - 查看 CloudWatch Logs
   - 檢查環境變數設定
   - 驗證網路配置

### 查看日誌
```bash
# 查看 CloudWatch Logs
aws logs tail /ecs/message-status --follow --region us-east-1

# 查看 ECS 任務日誌
aws ecs describe-tasks --cluster default --tasks TASK_ID --region us-east-1
```

## 架構圖

```
┌─────────────────┐    ┌─────────────────┐
│ StatusUpdateQueue│    │      DLQ        │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          │                      │
          └──────┬─────────────────┘
                 │
         ┌───────▼───────┐
         │ Message Status │
         │     Task       │
         │   (ECS/Fargate)│
         └───────┬───────┘
                 │
         ┌───────▼───────┐
         │   EventQueue  │
         └───────────────┘
```

## 版本歷史

- v1.0.0 - 初始版本
  - 基本的 SQS 訊息處理
  - Docker 化部署
  - ECS Fargate 支援
