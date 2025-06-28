# 使用官方 Python runtime 作為父映像
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製依賴檔案
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY src/ .

# 建立非 root 使用者
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# 設定環境變數
ENV APP_NAME=message-status
ENV LOG_LEVEL=INFO
ENV POLL_INTERVAL=10
ENV MAX_MESSAGES=10

# 健康檢查 - 檢查進程是否存在
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*app.py" || exit 1

# 運行應用程式
CMD ["python", "app.py"]
