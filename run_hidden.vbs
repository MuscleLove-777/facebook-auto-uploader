' Launch Facebook unmanned post with NO visible window (screen-quiet compliance).
Dim exitCode
exitCode = CreateObject("WScript.Shell").Run "cmd /c ""C:\facebook-auto-uploader\run_facebook_post.bat""", 0, True
WScript.Quit exitCode
