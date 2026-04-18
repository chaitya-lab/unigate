# Test full flow - Web to Telegram and Telegram to Web
$env:TELEGRAM_BOT_TOKEN = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
$proc = Start-Process python -ArgumentList "-m", "unigate", "start", "-f", "-c", "local.yaml", "-p", "8090" -NoNewWindow -PassThru
Start-Sleep 7

Write-Host "==========================================="
Write-Host "TEST 1: Send from WebUI"
Write-Host "==========================================="

# Send via webhook (this goes to web instance and routes to telegram)
try {
    $body = @{
        text = "Message from WebUI to Telegram!"
        sender = @{ id = "web"; name = "Web User" }
        session_id = "test-session"
    } | ConvertTo-Json
    
    $r = Invoke-WebRequest -Uri "http://localhost:8090/unigate/webhook/web" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5
    Write-Host "Send result:" $r.StatusCode
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Start-Sleep 3

Write-Host "==========================================="
Write-Host "TEST 2: Check Status"
Write-Host "==========================================="
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8090/unigate/status" -UseBasicParsing -TimeoutSec 5
    Write-Host "Status:" $r.Content
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Start-Sleep 2

Write-Host ""
Write-Host "==========================================="
Write-Host "NOW REPLY IN TELEGRAM - I'll poll"
Write-Host "==========================================="
Start-Sleep 15

Write-Host "==========================================="
Write-Host "TEST 3: Check Inbox"
Write-Host "==========================================="
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8090/unigate/status" -UseBasicParsing -TimeoutSec 5
    Write-Host "Final Status:" $r.Content
} catch {
    Write-Host "Error:" $_.Exception.Message
}

$proc.Kill()
Write-Host ""
Write-Host "DONE!"