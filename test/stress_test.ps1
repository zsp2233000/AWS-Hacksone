# 高負載壓力測試 (50個用戶，120秒)
param(
    [int]$Users = 50,
    [int]$SpawnRate = 5,
    [string]$Duration = "120s",
    [string]$ReportName = "stress_test_report"
)

Write-Output "開始執行高負載壓力測試..."
Write-Output "用戶數: $Users"
Write-Output "每秒產生用戶數: $SpawnRate"
Write-Output "測試時間: $Duration"
Write-Output "報告將儲存為: $ReportName.html"
Write-Output ""

Set-Location -Path $PSScriptRoot
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users $Users --spawn-rate $SpawnRate -t $Duration --headless --html="$ReportName.html" --csv="$ReportName"

Write-Output ""
Write-Output "測試完成！請查看報告檔案：$ReportName.html"
