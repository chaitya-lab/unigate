$proc = Start-Process python -ArgumentList "run_server.py" -NoNewWindow -PassThru
Start-Sleep 5

Write-Host "Testing UI..."
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/web" -UseBasicParsing -TimeoutSec 5
    Write-Host "UI Status:" $r.StatusCode
    Write-Host "UI Length:" $r.Content.Length
} catch {
    Write-Host "UI Error:" $_.Exception.Message
}

Write-Host "Testing send..."
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/send" -Method POST -ContentType "application/json" -Body '{"text":"From test!"}' -UseBasicParsing -TimeoutSec 5
    Write-Host "Send:" $r.Content
} catch {
    Write-Host "Send Error:" $_.Exception.Message
}

Write-Host "Testing poll..."
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8080/unigate/web/poll" -UseBasicParsing -TimeoutSec 5
    Write-Host "Poll:" $r.Content
} catch {
    Write-Host "Error:" $_.Exception.Message
}

Start-Sleep 3
Stop-Process $proc.Id -Force -ErrorAction SilentlyContinue