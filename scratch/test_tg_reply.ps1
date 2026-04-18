# Poll for messages from telegram
$env:TELEGRAM_BOT_TOKEN = "8674434491:AAEor504OZ97402INs9Qzao4hOKcYbEnpzU"
$proc = Start-Process python -ArgumentList "-m", "unigate", "start", "-f", "-c", "local.yaml", "-p", "8091" -NoNewWindow -PassThru
Start-Sleep 6

Write-Host "Server running. Send reply in Telegram now..."
Write-Host "Waiting 20 seconds..."
Start-Sleep 20

Write-Host "Checking status..."
$r = Invoke-WebRequest -Uri "http://localhost:8091/unigate/status" -UseBasicParsing
Write-Host $r.Content

$proc.Kill()