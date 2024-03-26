@echo off

REM This bat script is called from SuperSTEM.py via subprocess.popen and calls hashesNew.bat
REM
REM This bat script compresses a folder to an archive using 7zip
REM If OK Then tests the archive
REM IF OK Then runs the hashesNew  bat script to calculate hashes
REM 

REM expects 4 command line parameters:
REM archive name, folder to be compressed, hashes bat script, base root dir of New_Data
REM

set ZIP="C:\Program Files\7-Zip\7z.exe"

REM compression options:
set "compr=zip"
set "compr_meth=LZMA"
set "compr_lev=7"
set "dict_size=16m"
set "word_size=8"
set "no_cpu=20"

:: Use the first command line argument as the archiveName (filename including path)
set "archiveName=%~1"

:: Check if archiveName is provided
if "%archiveName%"=="" (
    echo Export path not provided.
    exit /b 1
)

:: Use the second command line argument as the folderPath (folder that is being compressed)
set "folderPath=%~2"

:: Check if folderPath is provided
if "%folderPath%"=="" (
    echo Folder path not provided.
    exit /b 1
)

:: Use the third command line argument as the hash command 
set "HASHES=%~3"

:: Check if folderPath is provided
if "%HASHES%"=="" (
    echo Hashes command not provided.
    exit /b 1
)

:: Use the fourth command line argument as the NEW_DATA root folder
set "NEW_DATA_ROOT=%~4"

:: Check if folderPath is provided
if "%NEW_DATA_ROOT%"=="" (
    echo New Data path not provided.
    exit /b 1
)

:: Get date and time in a filename-friendly format
:: Note: The format of %date% and %time% might vary based on system locale
:: The following is a common format but might need adjustment
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%b%%d)
for /f "tokens=1-5 delims=:." %%a in ('echo %time%') do (set mytime=%%a%%b%%c)

echo -
echo --- Compressing the folder... Start time: %time%

%ZIP% a -t%compr% -mm=%compr_meth% -m0=%compr_meth%:d%dict_size%:fb%word_size% -mx=%compr_lev% -mmt=%no_cpu% "%archiveName%" "%folderPath%"
if errorlevel 1 (
    echo Compression failed.
    exit /b 1
)
echo --- End time: %time%

echo -
echo --- Testing the archive...
%ZIP% t "%archiveName%"
if errorlevel 1 (
    echo Archive test failed.
    exit /b 1
)

echo -
echo --- Success: The folder was compressed and verified successfully.

echo -
echo --- Calculating hashes of New_Data ...
%HASHES% "%NEW_DATA_ROOT%"
if errorlevel 1 (
    echo Calculating hashes failed.
    exit /b 1
)
