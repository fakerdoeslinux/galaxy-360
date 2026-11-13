# galaxy-360's build on a Windows box with the Xbox 360 SDK. Run from the galaxy-360 checkout:
#
#   powershell -ExecutionPolicy Bypass -File scripts\build-360.ps1 -Tree C:\src\nebula -Build C:\build\x360
#
# It patches a Nebula checkout (both patches, in order, at the pinned commit), configures the console target against the
# SDK named by $env:XEDK, builds it, and (with -Package) lays out the folder the console boots.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tree,
    [string]$Build = "build\x360",
    [string]$Out = "dist\galaxy-360",
    [string]$Data = "",
    [string]$Configuration = "Release",
    [switch]$Package,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Pin = "4f40d95"

function Fail($Message) { Write-Error $Message; exit 1 }

# ---- The SDK ----------------------------------------------------------------------------------------------------

if (-not $env:XEDK) { Fail "Set XEDK to the Xbox 360 SDK's root (the folder holding bin\win32 and include\xbox360)." }
if (-not (Test-Path (Join-Path $env:XEDK "bin\win32\cl.exe"))) { Fail "No bin\win32\cl.exe under $env:XEDK: that is not an Xbox 360 SDK." }
Write-Host "SDK: $env:XEDK"

if (-not (Test-Path (Join-Path $Tree ".git"))) { Fail "$Tree is not a git checkout of Nebula." }

# ---- The patches ------------------------------------------------------------------------------------------------

Push-Location $Tree
try {
    $head = (git rev-parse --short HEAD).Trim()
    if ($head -ne $Pin) {
        Write-Host "Note: the tree is at $head, the patches are cut against $Pin. Continuing; git apply will say if it cannot."
    }
    foreach ($patch in @("0001-linux-port.patch", "0002-xbox360-platform.patch")) {
        $path = Join-Path $RepoRoot "patches\$patch"
        git apply --check $path 2>$null
        if ($LASTEXITCODE -eq 0) {
            git apply $path
            Write-Host "applied $patch"
        } else {
            # Already applied is the normal case on a second run: a reverse check tells the two apart.
            git apply --reverse --check $path 2>$null
            if ($LASTEXITCODE -eq 0) { Write-Host "already applied: $patch" }
            else { Fail "$patch does not apply to $Tree. Reset the tree to $Pin and try again." }
        }
    }
} finally {
    Pop-Location
}

# ---- Configure and build ----------------------------------------------------------------------------------------

$buildPath = Join-Path $Tree $Build
$configArgs = @(
    "-S", (Join-Path $Tree "platform\xbox360"),
    "-B", $buildPath,
    "-DCMAKE_TOOLCHAIN_FILE=$(Join-Path $Tree 'platform\xbox360\toolchain-xbox360.cmake')",
    "-DNEBULA_X360_RENDERER=ON",
    "-DNEBULA_RELEASE=ON"
)
if ($Clean -and (Test-Path $buildPath)) { Remove-Item -Recurse -Force $buildPath }

& cmake @configArgs
if ($LASTEXITCODE -ne 0) { Fail "configure failed" }
& cmake --build $buildPath --config $Configuration
if ($LASTEXITCODE -ne 0) { Fail "build failed" }

$xex = Get-ChildItem -Recurse -Filter "nebula_x360.xex" $buildPath | Select-Object -First 1
if (-not $xex) { Fail "the build produced no nebula_x360.xex (the renderer milestone is off?)" }
Write-Host "built $($xex.FullName)"

# ---- Package ----------------------------------------------------------------------------------------------------

if ($Package) {
    $arguments = @("scripts\package.py", "--xex", $xex.FullName, "--out", $Out)
    if ($Data) { $arguments += @("--data", $Data) }
    & python @arguments
    if ($LASTEXITCODE -ne 0) { Fail "packaging failed" }
}
