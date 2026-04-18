$proc = Start-Process python -ArgumentList "run.py" -NoNewWindow -PassThru -RedirectStandardOutput "server_out.txt" -RedirectStandardError "server_err.txt"
$proc.Id
Start-Sleep 5
if (Test-Path "server_out.txt") { Get-Content "server_out.txt" }
if (Test-Path "server_err.txt") { Get-Content "server_err.txt" }
Stop-Process $proc.Id -Force -ErrorAction SilentlyContinue