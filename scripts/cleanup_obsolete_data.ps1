param([switch]$Purge)
$ErrorActionPreference = 'Stop'
$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$archiveRoot = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $workspaceRoot) 'BTL_luu_tru_20261010'))
$verificationPath = Join-Path $workspaceRoot 'data/statistics/native512-v1/frontal512-verification.json'
$verification = Get-Content -LiteralPath $verificationPath -Raw | ConvertFrom-Json
if ($verification.images -ne 600 -or $verification.candidate_count -ne 500 -or $verification.maximum_vector_difference -ne 0 -or $verification.bundle_name -ne 'native512-v1' -or $verification.processed_dimensions[0] -ne 512) {
    throw 'The replacement dataset has not passed verification.'
}
$backupReport = Get-Content -LiteralPath (Join-Path $workspaceRoot 'data/backups/before-native512-20261010.json') -Raw | ConvertFrom-Json
$backupPath = Join-Path $workspaceRoot $backupReport.archive
if ((Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $backupReport.sha256) {
    throw 'Rollback backup checksum mismatch.'
}
$sourceRows = Import-Csv -LiteralPath (Join-Path $workspaceRoot 'data/manifests/frontal512_sources.csv') -Encoding UTF8
if ($sourceRows.Count -ne 600) { throw 'Source manifest is incomplete.' }
foreach ($row in $sourceRows) {
    $sourcePath = [System.IO.Path]::GetFullPath((Join-Path (Join-Path $workspaceRoot 'data') $row.relative_path))
    if (-not $sourcePath.StartsWith($workspaceRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Source path escapes workspace.' }
    if ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.source_sha256) {
        throw ('Replacement image checksum mismatch: ' + $row.relative_path)
    }
}
if ((Get-Item -LiteralPath $archiveRoot).Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'Archive root is a filesystem link.' }
$projectCleanupReportPath = Join-Path $workspaceRoot 'docs/project-cleanup-20261010.json'
$projectCleanupTarget = Join-Path $archiveRoot 'obsolete-after-project-cleanup'
if (Test-Path -LiteralPath $projectCleanupTarget) {
    if ((Get-Item -LiteralPath $projectCleanupTarget).Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'Project cleanup archive is a filesystem link.' }
    $projectCleanupLinks = Get-ChildItem -LiteralPath $projectCleanupTarget -Recurse -Force | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }
    if ($projectCleanupLinks) { throw 'Project cleanup archive contains filesystem links.' }
    $projectCleanupReport = Get-Content -LiteralPath $projectCleanupReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $projectCleanupReport.moved -or $projectCleanupReport.deleted) { throw 'Project cleanup archive is not verified.' }
    foreach ($entry in $projectCleanupReport.planned_files) {
        $entryPath = [System.IO.Path]::GetFullPath((Join-Path $projectCleanupTarget $entry.path))
        if (-not $entryPath.StartsWith($projectCleanupTarget + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup archive entry escapes target.' }
        if ((Get-FileHash -LiteralPath $entryPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
            throw ('Cleanup archive checksum mismatch: ' + $entry.path)
        }
    }
    $archivedFiles = @(Get-ChildItem -LiteralPath $projectCleanupTarget -File -Recurse -Force)
    if ($archivedFiles.Count -ne $projectCleanupReport.planned_files.Count) { throw 'Cleanup archive contains unplanned files.' }
}
$targets = @('unused/data', 'obsolete-after-frontal512', 'empty-after-frontal512', 'obsolete-after-native512', 'obsolete-after-project-cleanup')
foreach ($relativeTarget in $targets) {
    $targetPath = [System.IO.Path]::GetFullPath((Join-Path $archiveRoot $relativeTarget))
    if (-not (Test-Path -LiteralPath $targetPath)) { continue }
    $resolvedTarget = (Resolve-Path -LiteralPath $targetPath).ProviderPath
    if ((Get-Item -LiteralPath $resolvedTarget).Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'Deletion target is a filesystem link.' }
    if ($resolvedTarget -ne $targetPath -or -not $resolvedTarget.StartsWith($archiveRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw ('Unexpected deletion target: ' + $resolvedTarget)
    }
    $links = Get-ChildItem -LiteralPath $resolvedTarget -Recurse -Force | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }
    if ($links) { throw ('Refusing a directory containing filesystem links: ' + $resolvedTarget) }
    $measurement = Get-ChildItem -LiteralPath $resolvedTarget -File -Recurse -Force | Measure-Object -Property Length -Sum
    Write-Output ($resolvedTarget + ': files=' + $measurement.Count + '; bytes=' + $measurement.Sum)
    if ($Purge) {
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
        Write-Output ('Deleted: ' + $resolvedTarget)
    }
}
if (-not $Purge) { Write-Output 'Preview only. Use -Purge to delete these obsolete dataset directories.' }
