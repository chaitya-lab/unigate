$env:TELEGRAM_BOT_TOKEN = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
$proc = Start-Process python -ArgumentList "-m", "unigate", "start", "-f", "-c", "local.yaml", "-p", "8086" -NoNewWindow -PassThru
Start-Sleep 6

Write-Host "=== Open WebUI (check in browser) ==="
Write-Host "http://localhost:8086/unigate/web/web"

Start-Sleep 3

Write-Host "=== Using send endpoint ==="
# Use webui channel's internal send via webhook
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8086/unigate/webhook/web" -Method POST -ContentType "application/json" -Body '{"text":"Via webhook!"}' -UseBasicParsing -TimeoutSec 5
    Write-Host "Webhook:" $r.StatusCode
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Start-Sleep 3

Write-Host "=== Check status ==="
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8086/unigate/status" -UseBasicParsing -TimeoutSec 5
    Write-Host "Status:" $r.Content
} catch {
    Write-Host "Error:" $_.Exception.Message
}

$proc.Kill()