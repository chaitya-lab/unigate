# Check inbox for telegram messages
$env:TELEGRAM_BOT_TOKEN = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
$proc = Start-Process python -ArgumentList "-m", "unigate", "start", "-f", "-c", "local.yaml", "-p", "8092" -NoNewWindow -PassThru
Start-Sleep 6

Write-Host "=== Wait for Telegram message ==="
Start-Sleep 25

Write-Host "=== Check all endpoints ==="
Write-Host "Status:"
$r = Invoke-WebRequest -Uri "http://localhost:8092/unigate/status" -UseBasicParsing
Write-Host $r.Content

Write-Host "Web poll:"
$r = Invoke-WebRequest -Uri "http://localhost:8092/unigate/web/web/poll" -UseBasicParsing
Write-Host $r.Content

Write-Host "Instances:"
$r = Invoke-WebRequest -Uri "http://localhost:8092/unigate/instances" -UseBasicParsing
Write-Host $r.Content

$proc.Kill()