import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
MANIFEST_PATH = DATA_DIR / "manifest.json"
BUSCA_PATH = DATA_DIR / "busca.json"
LEGACY_PATH = PROJECT_ROOT / "transcricoes.json"
INFO_PATH = PROJECT_ROOT / "info.json"


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


def normalizar_texto_busca(text):
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def montar_indice_busca(transcricao):
    partes = []
    segmentos = []
    pos = 0

    for item in transcricao:
        bruto = re.sub(r" {2,}", " ", item.get("text") or "")
        norm = normalizar_texto_busca(bruto)
        if not norm:
            continue

        if partes:
            pos += 1

        segmentos.append([pos, int(item["tStartMs"])])
        partes.append(norm)
        pos += len(norm)

    texto = " ".join(partes)
    if not texto:
        return None

    return {"t": texto, "s": segmentos}


def carregar_indice_busca():
    if not BUSCA_PATH.exists():
        return {"versao": 1, "itens": {}}

    try:
        return carregar_json_seguro(BUSCA_PATH)
    except (json.JSONDecodeError, ValueError) as erro:
        print(f"Indice de busca invalido ({erro}), recriando...")
        return {"versao": 1, "itens": {}}


def atualizar_entrada_indice_busca(video_id, indice):
    busca = carregar_indice_busca()
    if indice:
        busca["itens"][video_id] = indice
    else:
        busca["itens"].pop(video_id, None)
    salvar_json_atomico(BUSCA_PATH, busca, indent=None)


def reconstruir_indice_busca():
    busca = {"versao": 1, "itens": {}}

    for arquivo in sorted(VIDEOS_DIR.glob("*.json")):
        try:
            video = carregar_json_seguro(arquivo)
        except (json.JSONDecodeError, ValueError):
            continue

        video_id = video.get("id") or arquivo.stem
        indice = montar_indice_busca(video.get("transcricao", []))
        if indice:
            busca["itens"][video_id] = indice

    salvar_json_atomico(BUSCA_PATH, busca, indent=None)
    print(f"Indice de busca atualizado: {len(busca['itens'])} videos")
    return busca


def salvar_video(video):
    video_id = video["id"]
    video = limpar_transcricao(dict(video))
    indice = montar_indice_busca(video.get("transcricao", []))
    if indice:
        video["busca"] = indice
    else:
        video.pop("busca", None)
    salvar_json_atomico(caminho_video(video_id), video, indent=None)
    atualizar_entrada_indice_busca(video_id, indice)
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


def zerar_banco():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    for arquivo in VIDEOS_DIR.glob("*.json"):
        arquivo.unlink()

    if BUSCA_PATH.exists():
        BUSCA_PATH.unlink()

    manifesto = manifesto_vazio()
    atualizar_manifesto(manifesto)
    print("Banco de dados zerado.")


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
        manifesto = carregar_manifesto()
    elif LEGACY_PATH.exists():
        migrar_arquivo_unico()
        manifesto = carregar_manifesto()
    else:
        manifesto = manifesto_vazio()
        atualizar_manifesto(manifesto)

    if not BUSCA_PATH.exists() and VIDEOS_DIR.exists() and any(VIDEOS_DIR.glob("*.json")):
        reconstruir_indice_busca()

    return manifesto
