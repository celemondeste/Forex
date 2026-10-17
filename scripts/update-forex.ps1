# Daily update for all forex pairs: pull the latest daily bars, then store a fresh prediction.
# Save as D:\Forex\scripts\update-forex.ps1
# Add any extra pairs you want kept fresh to $pairs (format EURUSD, no slash).

$base  = 'http://127.0.0.1:8000'
$pairs = @('EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD')

$envFile = Join-Path $PSScriptRoot '..\backend\.env'
$key = (Get-Content $envFile | Where-Object { $_ -like 'ADMIN_API_KEY=*' }) -replace '^ADMIN_API_KEY=', ''
$headers = @{ 'X-Admin-Key' = $key.Trim() }
$logFile = Join-Path $PSScriptRoot 'update-forex.log'

function Write-Log($message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $message" | Tee-Object -FilePath $logFile -Append
}

try {
    Invoke-RestMethod -Uri "$base/api/health" | Out-Null
} catch {
    Write-Log 'Backend is not running or database is unavailable - aborting'
    exit 1
}

foreach ($pair in $pairs) {
    try {
        $sync = Invoke-RestMethod -Method Post -Uri "$base/api/admin/sync/$pair" -Headers $headers
        Write-Log "$pair sync: $($sync.status) fetched=$($sync.rows_fetched) inserted=$($sync.rows_inserted) updated=$($sync.rows_updated)"
    } catch {
        Write-Log "$pair sync FAILED: $($_.Exception.Message)"
        continue
    }

    try {
        $pred = Invoke-RestMethod -Method Post -Uri "$base/api/admin/predict/$pair" -Headers $headers
        Write-Log "$pair predict: as_of=$($pred.as_of_timestamp) regime=$($pred.current_regime) signal=$($pred.signal)"
    } catch {
        Write-Log "$pair predict FAILED (no approved model yet?): $($_.Exception.Message)"
    }

    # Twelve Data free plan allows 8 requests per minute
    Start-Sleep -Seconds 15
}

Write-Log 'Done'
