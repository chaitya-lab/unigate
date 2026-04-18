$proc = Start-Process python -ArgumentList "run_server.py" -NoNewWindow -PassThru
Start-Sleep 3
Write-Host "=== Send from Web ==="
$r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/send" -Method POST -ContentType "application/json" -Body '{"text":"Test 456"}' -UseBasicParsing
Write-Host $r.Content

Write-Host ""
Write-Host "==========================================="
Write-Host "NOW - Please send a reply in Telegram."
Write-Host "I'll wait 30 seconds for you to type and send."
Write-Host "==========================================="

Start-Sleep 30

Write-Host "=== Check inbox ==="
$r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/inbox" -UseBasicParsing
Write-Host $r.Content

Stop-Process $proc.Id -Force -ErrorAction SilentlyContinue