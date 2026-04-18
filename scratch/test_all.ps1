$proc = Start-Process python -ArgumentList "run_server.py" -NoNewWindow -PassThru
Start-Sleep 3
Write-Host "=== 1. Send from Web ==="
$r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/send" -Method POST -ContentType "application/json" -Body '{"text":"Test 123"}' -UseBasicParsing
Write-Host $r.Content

Start-Sleep 2

Write-Host "=== 2. Check inbox ==="
$r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/inbox" -UseBasicParsing
Write-Host $r.Content

Write-Host "=== Now YOU send a message in Telegram ==="
Start-Sleep 10

Write-Host "=== 3. Check inbox after Telegram ==="
$r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/inbox" -UseBasicParsing
Write-Host $r.Content

Stop-Process $proc.Id -Force -ErrorAction SilentlyContinue