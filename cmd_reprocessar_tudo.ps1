$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

conda deactivate 2>$null
conda activate base

Write-Host "ATENCAO: Este modo apaga todo o banco de dados (data/videos, manifest.json, busca.json)."
$confirmacao = Read-Host "Digite SIM para continuar"
if ($confirmacao -ne "SIM") {
    Write-Host "Operacao cancelada."
    exit 0
}

python -m pip install -r requirements.txt -q
python scripts/ytsearch.py --reprocessar-tudo

if ($LASTEXITCODE -ne 0) {
    Write-Error "Reprocessamento completo falhou com codigo $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Reprocessamento completo concluido."
