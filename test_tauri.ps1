$outFile = "C:\Users\egidio\Desktop\Brasfoot\test_result.txt"
"=== Test started $(Get-Date) ===" | Out-File $outFile

# Kill any running instances
Get-Process | Where-Object { $_.ProcessName -match 'Ultrafoot|brasfoot' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 3

# Clear env var
Remove-Item Env:\BRASFOOT_PORT -ErrorAction SilentlyContinue

# Launch Tauri app normally
$p = Start-Process "$env:LOCALAPPDATA\Ultrafoot 26\Ultrafoot 26.exe" -PassThru
"Launched PID=$($p.Id)" | Out-File $outFile -Append
Start-Sleep 8

# Check if Tauri still running
$running = -not $p.HasExited
"After 8s: Running=$running" | Out-File $outFile -Append

if (-not $running) {
    "ExitCode=$($p.ExitCode)" | Out-File $outFile -Append
}

# Wait for sidecar extraction (total 75 seconds)
Start-Sleep 67

$running2 = -not $p.HasExited
"After 75s: Running=$running2" | Out-File $outFile -Append

# List processes
Get-Process | Where-Object { $_.ProcessName -match 'Ultrafoot|brasfoot' } | 
    Select-Object Id, ProcessName, MainWindowTitle |
    Format-Table -AutoSize |
    Out-String |
    Out-File $outFile -Append

# Find sidecar port
$connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | 
    Where-Object { $_.OwningProcess -in (Get-Process -Name 'brasfoot-server' -ErrorAction SilentlyContinue).Id }
if ($connections) {
    $port = $connections[0].LocalPort
    "Sidecar listening on port: $port" | Out-File $outFile -Append
    
    # Test requests
    try {
        $r = curl.exe -s -o NUL -w "%{http_code} %{size_download}" "http://127.0.0.1:${port}/Logo%20-%20UF26%20III.png"
        "Logo request: $r" | Out-File $outFile -Append
    } catch {
        "Logo request error: $_" | Out-File $outFile -Append
    }
    
    try {
        $r = curl.exe -s -o NUL -w "%{http_code} %{size_download}" "http://127.0.0.1:${port}/Fundo%20II.gif"
        "GIF request: $r" | Out-File $outFile -Append
    } catch {
        "GIF request error: $_" | Out-File $outFile -Append
    }
    
    try {
        $r = curl.exe -s -o NUL -w "%{http_code} %{size_download}" "http://127.0.0.1:${port}/api/ping" -X POST -d "[]" -H "Content-Type: application/json"
        "API ping: $r" | Out-File $outFile -Append
    } catch {
        "API ping error: $_" | Out-File $outFile -Append
    }
} else {
    "No sidecar listening port found" | Out-File $outFile -Append
}

"=== Test complete ===" | Out-File $outFile -Append
