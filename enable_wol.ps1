# Enable Wake-on-LAN on Windows (run as Administrator)
# Usage: right-click this file -> "Run with PowerShell" (as admin), or:
#   powershell -ExecutionPolicy Bypass -File enable_wol.ps1

$ErrorActionPreference = "Continue"

Write-Host "Enabling Wake-on-LAN..." -ForegroundColor Cyan

# 1) Set the NIC power-management flags (wake on magic packet + allow to wake)
Get-NetAdapter | Where-Object { $_.Status -eq "Up" -or $_.MediaType -eq "802.3" } | ForEach-Object {
    try {
        Set-NetAdapterPowerManagement -Name $_.Name -WakeOnMagicPacket Enabled -ErrorAction Stop
        Write-Host ("  [OK] WakeOnMagicPacket enabled on '" + $_.Name + "'") -ForegroundColor Green
    } catch {
        Write-Host ("  [!] Could not set WakeOnMagicPacket on '" + $_.Name + "': " + $_.Exception.Message) -ForegroundColor Yellow
    }
    try {
        Set-NetAdapterPowerManagement -Name $_.Name -AllowComputerToTurnOffDevice $false -ErrorAction Stop
        Write-Host ("  [OK] 'Allow computer to turn off this device' disabled on '" + $_.Name + "'") -ForegroundColor Green
    } catch {
        Write-Host ("  [!] AllowComputerToTurnOffDevice on '" + $_.Name + "': " + $_.Exception.Message) -ForegroundColor Yellow
    }
}

# 2) powercfg: explicitly arm the devices to wake the system
foreach ($dev in @("Wi-Fi", "Ethernet")) {
    powercfg /deviceenablewake $dev 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("  [OK] powercfg armed '" + $dev + "' to wake the PC") -ForegroundColor Green
    } else {
        Write-Host ("  [!] powercfg could not arm '" + $dev + "' (may need exact device name or BIOS)") -ForegroundColor Yellow
    }
}

# 3) Show which devices can now wake the PC
Write-Host ""
Write-Host "Devices armed to wake this PC:" -ForegroundColor Cyan
powercfg /devicequery wake_armed

Write-Host ""
Write-Host "Done. Remember: also enable 'Wake on LAN' / 'Power On By PCI-E' in BIOS," -ForegroundColor Yellow
Write-Host "and keep the PC on AC power (WoL needs the Ethernet/Wi-Fi radio powered)." -ForegroundColor Yellow
