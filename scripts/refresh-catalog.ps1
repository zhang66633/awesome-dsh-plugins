# refresh-catalog.ps1 — 商店目录快照一条龙刷新（供任务计划程序定时跑）
# 流程：雷达流水线 → 拷快照 → 重建 client bundle → 重打 tarball → profile 重装
# 日志追加到 $LOG；每一步失败都会记录但继续（单步失败不整死其余步骤）。

$ErrorActionPreference = 'Continue'
$radar  = 'D:\_Projects\skill_mcp\awesome-dsh-plugins'
$store  = 'D:\_Projects\skill_mcp\dsh-plugin-installer'
$prof   = "$env:USERPROFILE\.dsh\profiles\web"
$py     = 'C:/Python314/python.exe'
$LOG    = Join-Path $radar 'generated\refresh.log'

function Step($name, [scriptblock]$body) {
  Write-Output ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $name) | Tee-Object -FilePath $LOG -Append
  & $body
  Write-Output ("   exit={0}" -f $LASTEXITCODE) | Tee-Object -FilePath $LOG -Append
}

Step 'discover' { Set-Location $radar; & $py scripts/discover.py }
Step 'normalize' { & $py scripts/normalize.py }
Step 'aggregate' { & $py scripts/aggregate.py }
Step 'l1-scan' { & $py scripts/l1-scan.py --min-stars 3 }
Step 'export-store' { & $py scripts/export-store.py }

Step 'copy snapshot' {
  Copy-Item "$radar\generated\current\store.json" "$store\data\store.json" -Force
  Write-Output "   ok"
}

Step 'build client bundle' { Set-Location $store; npm run build }
Step 'repack tarball' { npm pack }

Step 'profile reinstall (pnpm update)' {
  Set-Location $prof
  $env:CI = 'true'
  pnpm update dsh-plugin-installer
}

Step 'repair link junctions (pnpm cross-drive bug)' {
  # pnpm 在 C: node_modules -> D: link: 目标时会生成损坏 junction（edge-case #16）。
  # 每次 pnpm install/update 后都可能复发：按 package.json 的 link: 声明逐个重建。
  $web = "$prof\node_modules"
  $manifest = Get-Content "$prof\package.json" -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($prop in $manifest.dependencies.PSObject.Properties) {
    $val = [string]$prop.Value
    if ($val -like 'link:*') {
      $name = $prop.Name
      $real = $val.Substring(5).Replace('/', '\')
      $link = Join-Path $web $name
      if (-not (Test-Path (Join-Path $link 'package.json'))) {
        if (Test-Path $link) { cmd /c rmdir /s /q "$link" 2>&1 | Out-Null }
        cmd /c mklink /J "$link" "$real" 2>&1 | Out-Null
        Write-Output "   repaired: $name -> $real"
      }
    }
  }
}
Write-Output ("[{0}] done（重启 dsh web 生效新快照）" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) | Tee-Object -FilePath $LOG -Append
