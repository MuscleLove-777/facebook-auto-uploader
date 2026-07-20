# Register Facebook auto-post tasks (hidden, power-safe, disabled until token verified)
if (-not (Test-Path "C:\facebook-auto-uploader")) {
  cmd /c mklink /J "C:\facebook-auto-uploader" "$PSScriptRoot" | Out-Null
}
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument '"C:\facebook-auto-uploader\run_hidden.vbs"'
$principal = New-ScheduledTaskPrincipal -UserId "atsus" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "FacebookAutoPost"  -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(9).AddMinutes(30)))  -Principal $principal -Description "facebook 09:30 hidden" -Force | Out-Null
Register-ScheduledTask -TaskName "FacebookAutoPost2" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(18).AddMinutes(30))) -Principal $principal -Description "facebook 18:30 hidden" -Force | Out-Null
foreach ($tn in "FacebookAutoPost","FacebookAutoPost2") {
  $t = Get-ScheduledTask -TaskName $tn
  $t.Settings.DisallowStartIfOnBatteries = $false
  $t.Settings.StopIfGoingOnBatteries     = $false
  $t.Settings.StartWhenAvailable         = $true
  Set-ScheduledTask -TaskName $tn -Settings $t.Settings | Out-Null
  Disable-ScheduledTask -TaskName $tn | Out-Null
}
Get-ScheduledTask -TaskName "FacebookAutoPost*" | ForEach-Object {
  $s = $_.Settings
  "{0,-18} {1,-9} {2}  battery_ok={3} catchUp={4}" -f $_.TaskName, $_.State, $_.Triggers[0].StartBoundary.Substring(11,5), (-not $s.DisallowStartIfOnBatteries), $s.StartWhenAvailable
}
