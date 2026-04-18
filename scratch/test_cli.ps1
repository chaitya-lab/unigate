$env:TELEGRAM_BOT_TOKEN = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
$proc = Start-Process python -ArgumentList "-m", "unigate", "start", "-f", "-c", "test_telegram.yaml", "-p", "8083" -NoNewWindow -PassThru
Start-Sleep 6

Write-Host "Testing..."
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8083/unigate/status" -UseBasicParsing -TimeoutSec 5
    Write-Host "Status:" $r.StatusCode
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Start-Sleep 1
$proc.Kill()