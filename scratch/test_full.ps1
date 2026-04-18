$proc = Start-Process python -ArgumentList "run_server.py" -NoNewWindow -PassThru -RedirectStandardOutput "server_log.txt"
Write-Host "Started server, pid:" $proc.Id
Start-Sleep 5

Write-Host "=== 1. Send message from Web ==="
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/send" -Method POST -UseBasicParsing -ContentType "application/json" -Body '{"text":"Hello from Web UI!"}' -TimeoutSec 5
    Write-Host "Send response:" $r.StatusCode $r.Content
} catch {
    Write-Host "Send Error:" $_.Exception.Message
}

Start-Sleep 3

Write-Host "=== 2. Check status ===" 
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/status" -UseBasicParsing -TimeoutSec 5
    Write-Host "Status:" $r.Content
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Write-Host "Done! Check Telegram for message."
Start-Sleep 2
Stop-Process $proc.Id -Force -ErrorAction SilentlyContinue