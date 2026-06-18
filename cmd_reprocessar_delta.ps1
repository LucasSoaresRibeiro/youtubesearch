$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

conda deactivate 2>$null
conda activate base

python -m pip install -r requirements.txt -q
python scripts/migrar_dados.py
python scripts/ytsearch.py --delta

if ($LASTEXITCODE -ne 0) {
    Write-Error "Reprocessamento delta falhou com codigo $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Reprocessamento delta concluido."
