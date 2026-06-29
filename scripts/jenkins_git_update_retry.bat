@echo off
setlocal EnableDelayedExpansion

REM 在 Jenkins 节点本地仓库目录执行，带重试的 git 更新（缓解 GitHub 443 偶发超时）
set "MAX_ATTEMPTS=%GIT_UPDATE_MAX_ATTEMPTS%"
set "WAIT_SECONDS=%GIT_UPDATE_WAIT_SECONDS%"
set "GIT_BRANCH=%GIT_BRANCH%"

if "%MAX_ATTEMPTS%"=="" set "MAX_ATTEMPTS=3"
if "%WAIT_SECONDS%"=="" set "WAIT_SECONDS=60"
if "%GIT_BRANCH%"=="" set "GIT_BRANCH=main"

set /a ATTEMPT=1

:retry_fetch
echo [%date% %time%] git fetch attempt !ATTEMPT!/%MAX_ATTEMPTS% (branch=%GIT_BRANCH%)
git fetch --tags --force --progress --prune origin +refs/heads/%GIT_BRANCH%:refs/remotes/origin/%GIT_BRANCH%
if errorlevel 1 goto fetch_failed

git checkout -B %GIT_BRANCH% origin/%GIT_BRANCH%
if errorlevel 1 goto fetch_failed

git pull --ff-only origin %GIT_BRANCH%
if errorlevel 1 goto fetch_failed

echo [%date% %time%] git update succeeded
exit /b 0

:fetch_failed
if !ATTEMPT! geq %MAX_ATTEMPTS% (
    echo [%date% %time%] git update failed after %MAX_ATTEMPTS% attempts
    exit /b 1
)
echo [%date% %time%] waiting %WAIT_SECONDS%s before retry...
timeout /t %WAIT_SECONDS% /nobreak >nul
set /a ATTEMPT+=1
goto retry_fetch
