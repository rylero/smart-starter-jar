$ErrorActionPreference = "Stop"

$project = "C:\Users\ryan\Projects\smart-starter-jar"
$log = Join-Path $project "pi\flash.log"
$status = Join-Path $project "pi\flash.status"
$exe = "C:\Program Files\Raspberry Pi Ltd\Imager\rpi-imager.exe"
$userdata = Join-Path $project "pi\cloud-init\user-data"
$netcfg = Join-Path $project "pi\cloud-init\network-config"
$image = Join-Path $project "pi\images\2026-10-06-raspios-trixie-arm64-lite.img.xz"
$diskNumber = 1
$dst = "\\.\PhysicalDrive$diskNumber"

function Write-Status($text) {
    $text | Set-Content -Path $status -Encoding utf8
    Add-Content -Path $log -Value "$(Get-Date -Format o) $text"
}

try {
    "" | Set-Content -Path $log -Encoding utf8
    Write-Status "starting"

    if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must run elevated."
    }

    $disk = Get-Disk -Number $diskNumber
    if ($disk.IsBoot -or $disk.IsSystem) { throw "Refusing to flash boot/system disk $diskNumber." }
    if ($disk.Size -lt 8GB -or $disk.Size -gt 64GB) { throw "Disk $diskNumber size $($disk.Size) is not a 8-64 GB SD card." }
    if ($disk.FriendlyName -notmatch "SD") { throw "Disk $diskNumber ($($disk.FriendlyName)) does not look like the SD reader." }
    if (-not (Test-Path $exe)) { throw "Raspberry Pi Imager not found: $exe" }
    if (-not (Test-Path $image)) { throw "Image not found: $image" }
    if (-not (Test-Path $userdata)) { throw "Missing user-data: $userdata" }
    if (-not (Test-Path $netcfg)) { throw "Missing network-config: $netcfg" }

    Write-Status "flashing disk $diskNumber ($($disk.FriendlyName), $([math]::Round($disk.Size/1GB,2)) GB)"

    $args = @(
        "--cli",
        "--disable-eject",
        "--debug",
        "--cloudinit-userdata", $userdata,
        "--cloudinit-networkconfig", $netcfg,
        $image,
        $dst
    )

    & $exe @args *>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Status "imager failed with exit $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    Write-Status "imager succeeded"
    exit 0
}
catch {
    Write-Status "error: $($_.Exception.Message)"
    exit 1
}
