# Renders screenshots/demo.gif from the scripted demo day in a real terminal: vhs tools/demo.tape
Output screenshots/demo.gif

Set Shell "bash"
Set FontSize 12
Set Width 1270
Set Height 690
Set Padding 0
Set Framerate 15
Set TypingSpeed 0

Hide
Type "export OFFICE_HOUR=11 COLORTERM=truecolor HERDR_PLUGIN_STATE_DIR=$(mktemp -d) && clear && bin/office --demo"
Enter
Sleep 400ms
Show

Sleep 7s

Tab
Sleep 2.5s
Tab
Sleep 3s
Escape
Sleep 1.5s

Type "m"
Sleep 1s
Down
Sleep 400ms
Down
Sleep 400ms
Down
Sleep 700ms
Up
Sleep 300ms
Up
Sleep 300ms
Up
Sleep 700ms
Space
Sleep 1.2s
Type "m"
Sleep 5s

Type "n"
Sleep 3s
Type "n"
Sleep 1s
