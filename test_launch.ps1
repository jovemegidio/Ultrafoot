$ErrorActionPreference = "SilentlyContinue"
$env:RUST_BACKTRACE = "1"
$appDir = "$env:LOCALAPPDATA\Ultrafoot"
$outFile = "$appDir\launch_test.log"

# Kill any existing processes
Get-Process *brasfoot*,*ultrafoot* 2>$null | Stop-Process -Force 2>$null
Start-Sleep 2

# Start and capture
$proc = Start-Process -FilePath "$appDir\brasfoot-ultimate.exe" -PassThru -RedirectStandardError "$appDir\launch_stderr.log" -RedirectStandardOutput "$appDir\launch_stdout.log"
$pid_val = $proc.Id
"Started PID: $pid_val" | Out-File $outFile

Start-Sleep 15

$exited = $proc.HasExited
"HasExited: $exited" | Out-File $outFile -Append

if (-not $exited) {
    "App is still running - SUCCESS!" | Out-File $outFile -Append
    Stop-Process -Id $pid_val -Force 2>$null
} else {
    "App exited early - FAILURE" | Out-File $outFile -Append
    "ExitCode: $($proc.ExitCode)" | Out-File $outFile -Append
}

Start-Sleep 2

# Capture stderr/stdout
"--- STDERR ---" | Out-File $outFile -Append
Get-Content "$appDir\launch_stderr.log" 2>$null | Out-File $outFile -Append
"--- STDOUT ---" | Out-File $outFile -Append
Get-Content "$appDir\launch_stdout.log" 2>$null | Out-File $outFile -Append
