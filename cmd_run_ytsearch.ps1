$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

conda deactivate 2>$null
conda activate base

python -m pip install -r requirements.txt -q
python migrar_dados.py
python ytsearch.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "ytsearch.py falhou com codigo $LASTEXITCODE"
    exit $LASTEXITCODE
}

git add data/ info.json index.html storage.py ytsearch.py migrar_dados.py requirements.txt .gitignore cmd_run_ytsearch.ps1
git diff --staged --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "feat: Auto backup"
    git push
} else {
    Write-Host "Nenhuma alteracao para commitar."
}

Start-Sleep -Seconds 15
