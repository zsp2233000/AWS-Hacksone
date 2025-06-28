# 啟動 Locust Web UI
Write-Output "正在啟動 Locust Web 介面..."
Write-Output "請在瀏覽器中打開 http://localhost:8089"
Write-Output "按 Ctrl+C 停止測試"
Write-Output ""

Set-Location -Path $PSScriptRoot
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws
