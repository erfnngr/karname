$ErrorActionPreference = 'Stop'
$companyRoot = Join-Path $env:APPDATA 'TaghvimMaliatiFA'
$destination = Join-Path $env:LOCALAPPDATA 'Programs\Karname'
$targetExe = Join-Path $destination 'Karname.exe'
$hostWasRunning = $false
$hostRestarted = $false
function Restart-CompanyHost {
    if (-not $script:hostWasRunning -or $script:hostRestarted -or -not (Test-Path -LiteralPath $script:targetExe)) { return }
    $hostArgs = @('--company-host','--host-root',('"{0}"' -f $script:companyRoot))
    Start-Process -FilePath $script:targetExe -ArgumentList $hostArgs -WindowStyle Hidden | Out-Null
    $hostDeadline = [DateTime]::UtcNow.AddSeconds(25)
    do {
        Start-Sleep -Milliseconds 500
        try { $newHostStatus = Get-Content -Raw -LiteralPath (Join-Path $script:companyRoot 'company-host-status.json') | ConvertFrom-Json } catch { $newHostStatus = $null }
        if ($newHostStatus -and $newHostStatus.running -and (Get-Process -Id ([int]$newHostStatus.pid) -ErrorAction SilentlyContinue)) { $script:hostRestarted = $true; return }
    } while ([DateTime]::UtcNow -lt $hostDeadline)
    throw 'مرکز شرکت پس از نصب دوباره راه‌اندازی نشد. تنظیمات مرکز شرکت را بررسی کنید.'
}
try {
    # Stop only the known installed host, cleanly, before replacing its executable.
    $statusPath = Join-Path $companyRoot 'company-host-status.json'
    if (Test-Path -LiteralPath $statusPath) {
        try { $hostStatus = Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json } catch { $hostStatus = $null }
        if ($hostStatus -and $hostStatus.running -and $hostStatus.pid) {
            $hostProcess = Get-Process -Id ([int]$hostStatus.pid) -ErrorAction SilentlyContinue
            if ($hostProcess -and $hostProcess.Path -and [IO.Path]::GetFullPath($hostProcess.Path) -eq [IO.Path]::GetFullPath($targetExe)) {
                $hostWasRunning = $true
                [IO.File]::WriteAllText((Join-Path $companyRoot 'company-host.stop'),'stop',[Text.Encoding]::ASCII)
                $deadline = [DateTime]::UtcNow.AddSeconds(15)
                while ((Get-Process -Id ([int]$hostStatus.pid) -ErrorAction SilentlyContinue) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 250 }
                if (Get-Process -Id ([int]$hostStatus.pid) -ErrorAction SilentlyContinue) { throw 'مرکز شرکت بسته نشد؛ نصب انجام نشد.' }
                Start-Sleep -Milliseconds 800
            }
        }
    }
    if (Get-Process -Name 'Karname','TaxCalendarFA' -ErrorAction SilentlyContinue) { throw 'ابتدا از منوی آیکن کنار ساعت، خروج کامل نسخه قبلی را بزنید و دوباره نصب را اجرا کنید.' }
    $sourceExe = Join-Path $PSScriptRoot 'Karname.exe'
    if (-not (Test-Path -LiteralPath $sourceExe)) { throw 'فایل Karname.exe کنار نصب‌کننده پیدا نشد. بسته را کامل از حالت فشرده خارج کنید.' }
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    if ([IO.Path]::GetFullPath($sourceExe) -ne [IO.Path]::GetFullPath($targetExe)) {
        Copy-Item -LiteralPath $sourceExe -Destination $targetExe -Force
    }
    foreach ($supportName in @('README_FA.md','FONT_LICENSE.txt','IRANSans-License.txt')) {
        $supportSource = Join-Path $PSScriptRoot $supportName
        $supportTarget = Join-Path $destination $supportName
        if ((Test-Path -LiteralPath $supportSource) -and ([IO.Path]::GetFullPath($supportSource) -ne [IO.Path]::GetFullPath($supportTarget))) {
            Copy-Item -LiteralPath $supportSource -Destination $supportTarget -Force
        }
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcutFolders = @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))
    foreach ($folder in $shortcutFolders) {
        # WScript shortcut persistence can reject a non-ASCII filename on some
        # Windows locales. Rename the completed file with the Unicode file API.
        $stagingLink = Join-Path $folder ('Karname-Setup-' + [Guid]::NewGuid().ToString('N') + '.lnk')
        $namedLink = Join-Path $folder 'کارنامه.lnk'
        $link = $shell.CreateShortcut($stagingLink)
        $link.TargetPath = $targetExe
        $link.Arguments = '--show'
        $link.WorkingDirectory = $destination
        $link.IconLocation = "$targetExe,0"
        $link.Save()
        Move-Item -LiteralPath $stagingLink -Destination $namedLink -Force
        $legacyLinkPath = Join-Path $folder 'Tax Calendar FA.lnk'
        if (Test-Path -LiteralPath $legacyLinkPath) {
            $legacyLink = $shell.CreateShortcut($legacyLinkPath)
            $legacyTarget = Join-Path $env:LOCALAPPDATA 'Programs\TaxCalendarFA\TaxCalendarFA.exe'
            if ($legacyLink.TargetPath -eq $legacyTarget) {
                $legacyLink.TargetPath = $targetExe
                $legacyLink.Arguments = '--show'
                $legacyLink.WorkingDirectory = $destination
                $legacyLink.IconLocation = "$targetExe,0"
                $legacyLink.Save()
            }
        }
    }
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    $existing = Get-ItemProperty -Path $runKey -Name 'TaghvimMaliatiFA' -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        New-ItemProperty -Path $runKey -Name 'TaghvimMaliatiFA' -Value ('"' + $targetExe + '" --tray') -PropertyType String -Force | Out-Null
    }
    Write-Host 'کارنامه نصب شد. میان‌بر آن روی دسکتاپ و منوی شروع آماده است.'
    Restart-CompanyHost
    Start-Process -FilePath $targetExe -ArgumentList '--show'
} catch {
    try { Restart-CompanyHost } catch { Write-Host 'راه‌اندازی دوباره مرکز شرکت انجام نشد؛ آن را از تنظیمات مرکز شرکت بررسی کنید.' }
    Write-Host ('نصب انجام نشد: ' + $_.Exception.Message)
    Write-Host 'می‌توانید Karname.exe را بدون نصب هم اجرا کنید.'
    exit 1
}
