@echo off

rem Add an alias for this script to your ".gitconfig" (use your own path):
rem
rem [alias]
rem		pr = !c:/projects/git-tools/git-pull-request/git-pull-request.bat
rem
rem Run the script as: "git pr"

"%~dp0\git-pull-request.py" %*