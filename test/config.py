# Locust 壓力測試配置檔案
# 可以直接在命令列使用這些參數

# 基本配置
HOST = "https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws"

# 測試場景配置
TEST_SCENARIOS = {
    "輕量測試": {
        "users": 5,
        "spawn_rate": 1,
        "run_time": "30s",
        "description": "5個併發用戶，每秒增加1個用戶，運行30秒"
    },
    "中等測試": {
        "users": 20,
        "spawn_rate": 2,
        "run_time": "60s",
        "description": "20個併發用戶，每秒增加2個用戶，運行60秒"
    },
    "高負載測試": {
        "users": 50,
        "spawn_rate": 5,
        "run_time": "120s",
        "description": "50個併發用戶，每秒增加5個用戶，運行120秒"
    },
    "壓力測試": {
        "users": 100,
        "spawn_rate": 10,
        "run_time": "180s",
        "description": "100個併發用戶，每秒增加10個用戶，運行180秒"
    }
}
