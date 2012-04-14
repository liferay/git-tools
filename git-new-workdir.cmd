@ECHO OFF

REM Create a GIT working directory for an existing repository
REM  %1 - Path of the existing repository
REM  %2 - Path of the new working directory
REM  %3 - Branch (optional)

IF #%1# == ## GOTO usage
IF #%2# == ## GOTO usage

SET GITCMD="%COMSPEC%" /c git
SET BRANCH=%3

REM Get source and destination folder
FOR %%d IN (%1) DO SET SRC=%%~fd
FOR %%d IN (%2) DO SET DST=%%~fd

REM Want to make sure that what is pointed to has a .git directory ...
PUSHD "%SRC%" 2>NUL
IF ERRORLEVEL 1 GOTO error_no_source

%GITCMD% rev-parse --git-dir 2>&1 >NUL
IF ERRORLEVEL 1 GOTO error_no_repository

REM Get full path to .git directory
FOR /F %%d IN ('%GITCMD% rev-parse --git-dir') DO SET GITDIR=%%~fd
POPD

REM Get a short name to prevent spaces
FOR %%f in ("%GITDIR%") DO SET GITSHORTDIR=%%~fsf

REM Don't link to a configured bare repository
FOR /F %%d IN ('%GITCMD% --git-dir=%GITSHORTDIR% config --bool --get core.bare') DO SET IS_BARE=%%d

IF #%IS_BARE%# == #true# GOTO error_bare

REM TODO: Check if the source is a working copy

REM Do not overwrite existing directories
IF EXIST "%DST%" GOTO error_destination_exists

REM Create the workdir and the logs sub dir
MKDIR "%DST%\.git\logs"
IF ERRORLEVEL 1 GOTO error_create_workdir

REM create the links to the original repo.  explicitly exclude index, HEAD and
REM logs/HEAD from the list since they are purely related to the current working
REM directory, and should not be shared.

REM Directories
FOR %%x in (refs logs\refs objects info hooks remotes rr-cache svn) DO (
	IF EXIST "%GITDIR%\%%x" (
		mklink /D "%DST%\.git\%%x" "%GITDIR%\%%x" 2>&1 >NUL
	)
)

REM Files
FOR %%x in (config packed-refs) DO (
	IF EXIST "%GITDIR%\%%x" (
		mklink "%DST%\.git\%%x" "%GITDIR%\%%x" 2>&1 >NUL
	)
)

REM Now setup the workdir
PUSHD "%DST%"

REM Copy the HEAD from the original repository as a default branch
COPY "%GITDIR%\HEAD" .git\HEAD >NUL

REM Checkout the branch (either the same as HEAD from the original repository, or
REM the one that was asked for)
%GITCMD% checkout -f %BRANCH%

ECHO Created work dir in "%DST%"
POPD

REM That's it
EXIT /B 0

REM ---- Error messages ----

:usage
ECHO Usage: %0 ^<repository^> ^<new_workdir^> [^<branch^>]
EXIT /B 127

:error_no_source
ECHO Directory not found: "%SRC%"
EXIT /B 128

:error_no_repository
ECHO Not a git repository: "%SRC%"
POPD
EXIT /B 128

:error_bare
ECHO "%SRC%" is a bare repository. 
EXIT /B 128

:error_destination_exists
ECHO Destination directory "%DST%" already exists
EXIT /B 128

:error_create_workdir
ECHO Unable to create "%DST%"!
EXIT /B 128