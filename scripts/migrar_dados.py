"""Migra transcricoes.json (arquivo unico) para data/manifest.json + data/videos/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from storage import garantir_estrutura, migrar_arquivo_unico, LEGACY_PATH, reconstruir_indice_busca

if __name__ == "__main__":
    if LEGACY_PATH.exists():
        migrar_arquivo_unico()
    else:
        garantir_estrutura()
        print("Estrutura de dados pronta.")

    reconstruir_indice_busca()
