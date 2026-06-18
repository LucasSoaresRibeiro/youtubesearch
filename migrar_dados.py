"""Migra transcricoes.json (arquivo unico) para data/manifest.json + data/videos/."""

from storage import garantir_estrutura, migrar_arquivo_unico, MANIFEST_PATH, LEGACY_PATH, reconstruir_indice_busca

if __name__ == "__main__":
    if LEGACY_PATH.exists():
        migrar_arquivo_unico()
    else:
        garantir_estrutura()
        print("Estrutura de dados pronta.")

    reconstruir_indice_busca()
