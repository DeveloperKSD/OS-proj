param(
  [string]$BaseUrl = 'http://127.0.0.1:5050',
  [string]$MetricsUrl = 'http://127.0.0.1:8000/metrics'
)
$ErrorActionPreference = 'Stop'
function Check([string]$Name, [scriptblock]$Action) {
  try { & $Action; Write-Host "[PASS] $Name" -ForegroundColor Green; return $true }
  catch { Write-Host "[FAIL] $Name -- $($_.Exception.Message)" -ForegroundColor Red; return $false }
}
$failed=0
if (-not (Check 'Health endpoint responds' { $r=Invoke-RestMethod "$BaseUrl/healthz" -TimeoutSec 8; if ($r.status -ne 'ok') { throw 'Unexpected health response' } })) { $failed++ }
if (-not (Check 'Status API has real sample fields' {
  $s=Invoke-RestMethod "$BaseUrl/api/status" -TimeoutSec 8
  foreach ($k in @('ready','environment','os_name','cpu_cores','ram_total_gb','cpu','per_core','mem','mem_used_gb','mem_total_gb','swap','rd','wr','net_up','net_down','top_cpu','top_memory','alerts','thresholds','sample_interval')) { if ($null -eq $s.$k) { throw "Missing field: $k" } }
  if (-not $s.ready) { throw 'Sampler has not produced a sample yet; wait for one interval and retry.' }
  if ($s.cpu -lt 0 -or $s.cpu -gt 100) { throw 'CPU outside 0..100' }
})) { $failed++ }
if (-not (Check 'History endpoint responds' { $h=Invoke-RestMethod "$BaseUrl/api/history" -TimeoutSec 8; if ($null -eq $h) { throw 'No history response' } })) { $failed++ }
if (-not (Check 'Config endpoint responds' { $c=Invoke-RestMethod "$BaseUrl/api/config" -TimeoutSec 8; if ($null -eq $c.thresholds) { throw 'Missing thresholds' } })) { $failed++ }
if (-not (Check 'Stress status endpoint responds' { $s=Invoke-RestMethod "$BaseUrl/api/stress/status" -TimeoutSec 8; if ($null -eq $s.active) { throw 'Missing active field' } })) { $failed++ }
if (-not (Check 'Prometheus metrics endpoint responds' { $m=Invoke-WebRequest $MetricsUrl -TimeoutSec 8; if ($m.Content -notmatch 'os_cpu_percent' -or $m.Content -notmatch 'os_network_download_bytes_per_s') { throw 'Expected metrics missing' } })) { $failed++ }
Write-Host ''
if ($failed -eq 0) { Write-Host 'All endpoint checks passed.' -ForegroundColor Green; exit 0 }
Write-Host "$failed check(s) failed. Check app logs and wait for a sample." -ForegroundColor Red
exit 1
