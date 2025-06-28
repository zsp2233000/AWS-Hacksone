# 快速輕量測試 (5個用戶，30秒)
param(
    [int]$Users = 5,
    [int]$SpawnRate = 1,
    [string]$Duration = "30s"
)

Write-Output "開始執行輕量壓力測試..."
Write-Output "用戶數: $Users"
Write-Output "每秒產生用戶數: $SpawnRate" 
Write-Output "測試時間: $Duration"
Write-Output ""

Set-Location -Path $PSScriptRoot
C:/Users/zsp22/AppData/Local/Programs/Python/Python313/python.exe -m locust -f locustfile.py --host=https://64awf2ej6to4zupffkcwqehvzm0djsnr.lambda-url.ap-southeast-1.on.aws --users $Users --spawn-rate $SpawnRate -t $Duration --headless
