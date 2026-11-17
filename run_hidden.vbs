' Launch Facebook unmanned post with NO visible window (screen-quiet compliance).
Option Explicit
On Error Resume Next
Dim shell, fso, diag, exitCode, runError, receiptError, compatExit, compatError
Dim privateRoot, runId, statusPath, stderrPath, stdoutPath, receipt, outputFile, quote, command
Dim lockPath, lockFile, lockWaitStarted, lockOwned, lockOwner, lockReleaseError
Set fso = CreateObject("Scripting.FileSystemObject")
If Err.Number <> 0 Then WScript.Quit 4
' Private per-run evidence must never enter uploader commits/content_pool.
privateRoot = "C:\Users\atsus\000_ClaudeCode\40_MuscleLove\dashboard\autonomy\state\facebook_wrapper_runs"
If Not fso.FolderExists(privateRoot) Then fso.CreateFolder privateRoot
If Err.Number <> 0 Then WScript.Quit 4
runId = Replace(fso.GetTempName, ".", "_")
statusPath = privateRoot & "\" & runId & ".status.log"
stderrPath = privateRoot & "\" & runId & ".stderr.log"
stdoutPath = privateRoot & "\" & runId & ".stdout.log"
lockPath = privateRoot & "\publisher.lock"
lockOwned = False
' Create without overwrite: even an ID collision cannot lose another receipt.
Set receipt = fso.CreateTextFile(statusPath, False)
If Err.Number <> 0 Then WScript.Quit 4
receipt.WriteLine Now & " start run_id=" & runId & " timezone=Asia/Tokyo"
If Err.Number <> 0 Then WScript.Quit 4

' Reserve this run's output without replacing any earlier evidence.
Set outputFile = fso.CreateTextFile(stdoutPath, False)
If Err.Number <> 0 Then WScript.Quit 4
outputFile.Close
If Err.Number <> 0 Then WScript.Quit 4

' Retain the existing shared status log as best-effort compatibility output.
Set diag = fso.OpenTextFile("C:\facebook-auto-uploader\wrapper_status.log", 8, True)
diag.WriteLine Now & " start"
diag.Close
Err.Clear
Set shell = CreateObject("WScript.Shell")
If Err.Number <> 0 Then WScript.Quit 4
quote = Chr(34)
' Serialize the real child; never steal an existing or stale owner's lock.
lockWaitStarted = Now
Do
  Err.Clear
  Set lockFile = fso.CreateTextFile(lockPath, False)
  If Err.Number = 0 Then
    lockOwned = True
    lockFile.WriteLine runId
    lockFile.Close
    If Err.Number <> 0 Then
      receipt.WriteLine Now & " lock_acquire_failed"
      receipt.Close
      WScript.Quit 4
    End If
    Exit Do
  End If
  Err.Clear
  If Not fso.FileExists(lockPath) Then
    receipt.WriteLine Now & " lock_acquire_failed"
    receipt.Close
    WScript.Quit 4
  End If
  If DateDiff("s", lockWaitStarted, Now) >= 3600 Then
    receipt.WriteLine Now & " lock_wait_timeout"
    receipt.Close
    WScript.Quit 4
  End If
  WScript.Sleep 1000
Loop
Err.Clear
' Capture child output per run; only outer-shell errors use stderrPath.
command = "cmd /c " & quote & quote & "C:\facebook-auto-uploader\run_facebook_post.bat" & quote & " " & quote & stdoutPath & quote & " 2> " & quote & stderrPath & quote & quote
exitCode = shell.Run(command, 0, True)
' Preserve the launch error before any logging can replace Err.Number.
runError = Err.Number
Err.Clear
If runError <> 0 Then
  receipt.WriteLine Now & " wrapper_error=" & runError
Else
  receipt.WriteLine Now & " child_exit=" & exitCode
End If
receiptError = Err.Number
Err.Clear
' Release only this process's token; a foreign owner's lock is untouched.
lockReleaseError = 0
If lockOwned Then
  Set lockFile = fso.OpenTextFile(lockPath, 1, False)
  lockOwner = lockFile.ReadLine
  lockFile.Close
  If Err.Number <> 0 Then
    lockReleaseError = 1
  ElseIf lockOwner <> runId Then
    lockReleaseError = 1
  Else
    fso.DeleteFile lockPath, False
    If Err.Number <> 0 Then lockReleaseError = 1
  End If
End If
Err.Clear
If lockReleaseError <> 0 Then
  receipt.WriteLine Now & " lock_release_failed"
  If Err.Number <> 0 Then receiptError = Err.Number
End If
Err.Clear
' Byte-preserving compatibility copy after the child has finished.
' A busy shared log cannot affect the child or discard private evidence.
command = "cmd /c " & quote & "type " & quote & stdoutPath & quote & " >> " & quote & "C:\facebook-auto-uploader\facebook_post_log.txt" & quote & " 2>nul" & quote
compatExit = shell.Run(command, 0, True)
compatError = Err.Number
Err.Clear
If compatError <> 0 Or compatExit <> 0 Then
  receipt.WriteLine Now & " compat_log_append_failed"
  If Err.Number <> 0 Then receiptError = Err.Number
End If
Err.Clear
receipt.Close
If Err.Number <> 0 Then receiptError = Err.Number
Err.Clear
Set diag = fso.OpenTextFile("C:\facebook-auto-uploader\wrapper_status.log", 8, True)
If runError <> 0 Then
  diag.WriteLine Now & " wrapper_error=" & runError
Else
  diag.WriteLine Now & " child_exit=" & exitCode
End If
diag.Close
If runError <> 0 Or receiptError <> 0 Or lockReleaseError <> 0 Then WScript.Quit 4
WScript.Quit exitCode
