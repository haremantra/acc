# Install the acc skill for Claude Code (Windows, PowerShell).
#
# Symlinks this checkout into your Claude skills dir so /acc resolves in any
# project, then verifies the install. Re-runnable (idempotent).
#
#   ./install.ps1            # symlink (needs Developer Mode or an elevated shell)
#   ./install.ps1 -Copy      # copy files instead of symlinking
#
# Uninstall: remove the folder it reports below, or run `make uninstall` (bash).
[CmdletBinding()]
param([switch]$Copy)

$ErrorActionPreference = "Stop"

$Src = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsDir = if ($env:CLAUDE_SKILLS_DIR) { $env:CLAUDE_SKILLS_DIR } else { Join-Path $HOME ".claude\skills" }
$Dest = Join-Path $SkillsDir "acc"

if (-not (Test-Path (Join-Path $Src "SKILL.md"))) {
    Write-Error "$Src doesn't look like the acc skill (no SKILL.md)"
}

New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null

# Clear a prior install.
if (Test-Path $Dest) {
    $item = Get-Item $Dest -Force
    if ($item.LinkType -or $Copy) {
        Remove-Item $Dest -Recurse -Force
    } else {
        Write-Error "$Dest already exists and is not a symlink. Remove it first to reinstall."
    }
}

if ($Copy) {
    Copy-Item -Recurse $Src $Dest
} else {
    # Directory symlink; requires Developer Mode or an elevated prompt.
    New-Item -ItemType SymbolicLink -Path $Dest -Target $Src | Out-Null
}

if (Test-Path (Join-Path $Dest "SKILL.md")) {
    $mode = if ($Copy) { "copy" } else { "symlink" }
    Write-Host "Installed acc ($mode) -> $Dest"
    Write-Host "Open Claude Code in any project and run /acc to confirm."
} else {
    Write-Error "install verification failed; SKILL.md missing under $Dest"
}
