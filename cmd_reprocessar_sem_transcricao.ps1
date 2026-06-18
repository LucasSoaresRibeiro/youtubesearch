$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

conda deactivate 2>$null
conda activate base

python -m pip install -r requirements.txt -q
python scripts/ytsearch.py --reprocessar-sem-transcricao

if ($LASTEXITCODE -ne 0) {
    Write-Error "Reprocessamento sem transcricao falhou com codigo $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Reprocessamento sem transcricao concluido."
