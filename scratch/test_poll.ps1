$proc = Start-Process python -ArgumentList "run_server.py" -NoNewWindow -PassThru
Write-Host "Server started. Now send a message in Telegram."
Write-Host "Press Enter to check poll..."
Read-Host "Waiting..."

Write-Host "Checking poll..."
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/poll" -UseBasicParsing -TimeoutSec 5
    Write-Host "Poll:" $r.Content
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Stop-Process $proc.Id -Force -ErrorAction SilentlyContinue