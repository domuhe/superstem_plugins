@ECHO OFF

REM This bat script is called from compress.bat
REM
REM it calculates and writes SHA256 hashes, file size and relative path filenames to output file
REM the root dir for the New_Data folder location is passed to the batch script via
REM command line parameter
REM
REM Output file is written to New_Data folder, ready to be uploaded via GoodSync
REM ==================================================================================
REM echo "Calculating HASHES of New Data"

Setlocal EnableDelayedExpansion

REM Use the first command line argument as the  root directory to search subdirectories from
set "ROOT_DIR=%~1"
REM set "ROOT_DIR=F:\StaffData\dmuecke\Nionswift-Development\New Data"

set "YEAR=%DATE:~-4%"
set "MONTH=%DATE:~3,2%"
set "DAY=%DATE:~0,2%"
set "HOUR=%TIME:~0,2%"
set "MINUTE=%TIME:~3,2%"
set "SECOND=%TIME:~6,2%"

REM Ensure hour is two digits (leading zero for single digit hours)
if "%HOUR:~0,1%"==" " set "HOUR=0%HOUR:~1,1%"

set "NOW=%YEAR%%MONTH%%DAY%-%HOUR%%MINUTE%%SECOND%

REM Set the output file name
echo -
set "OUTPUT_FILE=%ROOT_DIR%\hashes_sstem3_%NOW%.txt"
echo --- Output file %OUTPUT_FILE%

REM Check if output file already exists and delete it to start fresh, EXCLUDE gsdata
REM if exist %OUTPUT_FILE% del %OUTPUT_FILE%

REM Loop through all files in the subdirectories of the specified root directory
for /r "%ROOT_DIR%" %%i in (*) do (

    REM Check if the file path contains _gsdata_
    echo %%i | findstr /C:"_gsdata_" > nul
    if !errorlevel! equ 0 (
        REM Skip this file as it's in the _gsdata_ folder
        echo Skipping: %%i
    ) else (
        REM Process file as it's not in the _gsdata_ folder
        echo Processing: %%i

        REM Get the file size in bytes
        set "FILESIZE=%%~zi"

        REM Calculate SHA-256 hash of the file
        for /f "tokens=1,* delims=:" %%a in ('certutil -hashfile "%%i" SHA256 ^| find /v "CertUtil"') do (
            set "HASH=%%a"
            set "FILE=%%i"

            REM Check if the variable begins with "SHA256"
            if "!HASH:~0,6!"=="SHA256" (
                REM echo The variable begins with SHA256.
            ) else (
                REM echo The variable does NOT begin with SHA256.
                    REM Strip the ROOT_DIR from the file path to make it relative
                set "RELATIVE_FILE=!FILE:%ROOT_DIR%\=!"

                REM Format and write the relative file path and hash to the output file
                echo !RELATIVE_FILE! !HASH! !FILESIZE! >> "%OUTPUT_FILE%"
            )
        )
    )
)

REM echo Hash values written to %OUTPUT_FILE%

