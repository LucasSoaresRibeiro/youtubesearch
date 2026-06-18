import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DATA_DIR = Path("data")
VIDEOS_DIR = DATA_DIR / "videos"
MANIFEST_PATH = DATA_DIR / "manifest.json"
LEGACY_PATH = Path("transcricoes.json")
INFO_PATH = Path("info.json")


def extrair_video_id(url):
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/").split("/")[0]
    return parse_qs(parsed.query).get("v", [None])[0]


def salvar_json_atomico(caminho, dados, indent=2):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")

    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=indent)
        arquivo.flush()
        os.fsync(arquivo.fileno())

    with open(temporario, encoding="utf-8") as arquivo:
        json.load(arquivo)

    os.replace(temporario, caminho)


def carregar_json_seguro(caminho):
    caminho = Path(caminho)
    with open(caminho, encoding="utf-8") as arquivo:
        conteudo = arquivo.read()

    try:
        return json.loads(conteudo)
    except json.JSONDecodeError:
        return reparar_json_array(conteudo)


def reparar_json_array(texto):
    texto = texto.rstrip()
    if not texto:
        raise ValueError("Arquivo JSON vazio")

    while texto:
        tentativa = texto
        if not tentativa.endswith("]"):
            if tentativa.endswith(","):
                tentativa = tentativa[:-1]
            tentativa += "]"

        try:
            dados = json.loads(tentativa)
            if isinstance(dados, list):
                print(f"JSON reparado: {len(dados)} itens recuperados")
                return dados
        except json.JSONDecodeError:
            pass

        indice = texto.rfind("},")
        if indice == -1:
            break
        texto = texto[: indice + 1]

    raise ValueError("Nao foi possivel reparar o arquivo JSON")


def manifesto_vazio():
    return {
        "versao": 1,
        "videos": 0,
        "dataExecucao": datetime.today().strftime("%d/%m/%Y"),
        "itens": [],
    }


def carregar_manifesto():
    if not MANIFEST_PATH.exists():
        return manifesto_vazio()

    try:
        return carregar_json_seguro(MANIFEST_PATH)
    except (json.JSONDecodeError, ValueError) as erro:
        print(f"Manifesto invalido ({erro}), recriando...")
        return manifesto_vazio()


def caminho_video(video_id):
    return VIDEOS_DIR / f"{video_id}.json"


def limpar_transcricao(video):
    video["transcricao"] = [
        item for item in video.get("transcricao", []) if item.get("text") and len(item["text"]) > 1
    ]
    return video


def salvar_video(video):
    video_id = video["id"]
    video = limpar_transcricao(dict(video))
    salvar_json_atomico(caminho_video(video_id), video, indent=None)
    return video


def carregar_video(video_id):
    caminho = caminho_video(video_id)
    if not caminho.exists():
        return None
    return carregar_json_seguro(caminho)


def atualizar_manifesto(manifesto):
    manifesto["videos"] = len(manifesto["itens"])
    manifesto["dataExecucao"] = datetime.today().strftime("%d/%m/%Y")
    salvar_json_atomico(MANIFEST_PATH, manifesto)
    salvar_json_atomico(
        INFO_PATH,
        {"videos": manifesto["videos"], "dataExecucao": manifesto["dataExecucao"]},
    )


def registrar_video(manifesto, video):
    possui_transcricao = video.get("possui_transcricao", len(video.get("transcricao", [])) > 0)
    item_manifesto = {
        "id": video["id"],
        "url": video["url"],
        "titulo": video["titulo"],
        "possui_transcricao": possui_transcricao,
    }
    video["possui_transcricao"] = possui_transcricao
    manifesto["itens"] = [item for item in manifesto["itens"] if item["id"] != video["id"]]
    manifesto["itens"].insert(0, item_manifesto)
    salvar_video(video)
    atualizar_manifesto(manifesto)


def buscar_video_cadastrado(manifesto, video_id):
    item = next((item for item in manifesto["itens"] if item["id"] == video_id), None)
    if not item:
        return None
    return carregar_video(video_id)


def migrar_arquivo_unico(caminho=LEGACY_PATH):
    caminho = Path(caminho)
    if not caminho.exists():
        return False

    print(f"Migrando {caminho} para {DATA_DIR}/...")
    transcricoes = carregar_json_seguro(caminho)

    videos_por_id = {}
    for video in transcricoes:
        video_id = video.get("id") or extrair_video_id(video.get("url", ""))
        if not video_id:
            continue
        video["id"] = video_id
        existente = videos_por_id.get(video_id)
        if not existente or len(video.get("transcricao", [])) > len(existente.get("transcricao", [])):
            videos_por_id[video_id] = video

    manifesto = carregar_manifesto() if MANIFEST_PATH.exists() else manifesto_vazio()
    ids_migrados = {item["id"] for item in manifesto["itens"]}
    videos_unicos = list(videos_por_id.values())
    print(f"  {len(transcricoes)} entradas -> {len(videos_unicos)} videos unicos")

    for indice, video in enumerate(videos_unicos, start=1):
        video_id = video["id"]
        if video_id in ids_migrados:
            existente = carregar_video(video_id)
            if existente and len(existente.get("transcricao", [])) >= len(video.get("transcricao", [])):
                continue

        registrar_video(manifesto, video)
        ids_migrados.add(video_id)
        if indice % 50 == 0:
            print(f"  {indice}/{len(videos_unicos)} migrados...")

    legado_backup = caminho.with_suffix(".json.bak")
    if legado_backup.exists():
        legado_backup.unlink()
    caminho.rename(legado_backup)
    print(f"Migracao concluida: {manifesto['videos']} videos em {VIDEOS_DIR}")
    return True


def garantir_estrutura():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    if MANIFEST_PATH.exists():
        return carregar_manifesto()

    if LEGACY_PATH.exists():
        migrar_arquivo_unico()
        return carregar_manifesto()

    manifesto = manifesto_vazio()
    atualizar_manifesto(manifesto)
    return manifesto
