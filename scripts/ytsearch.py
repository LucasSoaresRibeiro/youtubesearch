import argparse
import re
import sys
import time
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from storage import (
    buscar_video_cadastrado,
    extrair_video_id,
    garantir_estrutura,
    reconstruir_indice_busca,
    registrar_video,
    zerar_banco,
)

IDIOMAS_PREFERIDOS = ["pt", "pt-BR", "pt-PT"]
MAX_TENTATIVAS_TRANSCRICAO = 3
PAUSA_ENTRE_TENTATIVAS = 2
URL_DO_CANAL = "https://www.youtube.com/@IBMaranata/streams"

_transcript_api = YouTubeTranscriptApi()


def normalizar_url(url):
    video_id = extrair_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url


def limpar_texto(text):
    text = text.replace("\n", " ")
    text = re.sub(r"♪|'|\"|\.{2,}|<[^>]*>|\{[^}]*\}|\[[^\]]*\]", "", text)
    return text.strip()


def _idioma_portugues(codigo):
    codigo = (codigo or "").lower()
    return codigo == "pt" or codigo.startswith("pt-")


def _selecionar_transcricao_pt(transcript_list):
    try:
        return transcript_list.find_transcript(IDIOMAS_PREFERIDOS)
    except NoTranscriptFound:
        pass

    for transcript in transcript_list:
        if _idioma_portugues(transcript.language_code):
            return transcript

    raise NoTranscriptFound(
        transcript_list.video_id,
        IDIOMAS_PREFERIDOS,
        transcript_list,
    )


def _formatar_transcricao(fetched):
    return [
        {
            "tStartMs": int(snippet.start * 1000),
            "text": limpar_texto(snippet.text),
        }
        for snippet in fetched
        if limpar_texto(snippet.text)
    ]


def buscar_transcricao(video_url):
    video_id = extrair_video_id(video_url)
    if not video_id:
        raise ValueError(f"Nao foi possivel extrair o ID do video: {video_url}")

    ultimo_erro = None
    for tentativa in range(MAX_TENTATIVAS_TRANSCRICAO):
        try:
            transcript_list = _transcript_api.list(video_id)
            transcript = _selecionar_transcricao_pt(transcript_list)
            return _formatar_transcricao(transcript.fetch())
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
            raise
        except CouldNotRetrieveTranscript as erro:
            ultimo_erro = erro
            if tentativa < MAX_TENTATIVAS_TRANSCRICAO - 1:
                pausa = PAUSA_ENTRE_TENTATIVAS * (tentativa + 1)
                print(f"Tentativa {tentativa + 1}/{MAX_TENTATIVAS_TRANSCRICAO} falhou para {video_id}, aguardando {pausa}s...")
                time.sleep(pausa)

    raise ultimo_erro


def criar_item_video(video_id, video_url, titulo, transcricao):
    return {
        "id": video_id,
        "url": video_url,
        "titulo": titulo,
        "possui_transcricao": len(transcricao) > 0,
        "transcricao": transcricao,
    }


def processar_transcricao_video(manifesto, video_id, video_url, titulo):
    video_cadastrado = buscar_video_cadastrado(manifesto, video_id)

    try:
        transcricao = buscar_transcricao(video_url)
        video_item = criar_item_video(video_id, video_url, titulo, transcricao)
        registrar_video(manifesto, video_item)

        if transcricao:
            print(f"Transcricao obtida: {len(transcricao)} segmentos (salvo em data/videos/{video_id}.json)")
        else:
            print(f"Transcricao vazia apos limpeza: {video_url}")

        return len(transcricao) > 0

    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as erro:
        print(f"Sem transcricao para {video_url}: {erro}")
        if not video_cadastrado:
            registrar_video(
                manifesto,
                criar_item_video(video_id, video_url, titulo, []),
            )
        return False

    except CouldNotRetrieveTranscript as erro:
        print(f"Erro ao obter a transcricao do video {video_url}: {erro}")
        if not video_cadastrado:
            registrar_video(
                manifesto,
                criar_item_video(video_id, video_url, titulo, []),
            )
        return False

    except Exception as erro:
        print(f"Erro inesperado ao obter a transcricao do video {video_url}: {erro}")
        return False


def listar_videos_canal(canal_url):
    opcoes = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignoreerrors": True,
    }

    videos_por_id = {}
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        resultado = ydl.extract_info(canal_url, download=False)

    if not resultado:
        return []

    for entry in resultado.get("entries") or []:
        if not entry:
            continue

        video_id = entry.get("id") or extrair_video_id(entry.get("url") or entry.get("webpage_url") or "")
        if not video_id:
            continue

        titulo = (entry.get("title") or "").strip() or video_id
        url = entry.get("webpage_url") or entry.get("url") or f"https://www.youtube.com/watch?v={video_id}"
        if not str(url).startswith("http"):
            url = f"https://www.youtube.com/watch?v={video_id}"

        videos_por_id[video_id] = {"titulo": titulo, "url": url}

    videos = list(videos_por_id.values())
    print(f"Videos encontrados no canal: {len(videos)}")
    return videos


def _processar_lista_canal(manifesto, video_urls, filtro):
    if not video_urls:
        print("Nenhum video para processar.")
        return 0

    processados = 0

    for indice, video_url_obj in enumerate(video_urls, start=1):
        print("-" * 20)
        print(f"Processando {indice}/{len(video_urls)} ...")

        video_url = normalizar_url(video_url_obj["url"])
        video_id = extrair_video_id(video_url)
        if not video_id:
            print(f"URL invalida: {video_url}")
            continue

        if not filtro(manifesto, video_id, video_url_obj):
            continue

        processar_transcricao_video(manifesto, video_id, video_url, video_url_obj["titulo"])
        processados += 1

    return processados


def reprocessar_tudo(canal_url=URL_DO_CANAL):
    print("Zerando banco de dados...")
    zerar_banco()
    manifesto = garantir_estrutura()

    video_urls = listar_videos_canal(canal_url)
    if not video_urls:
        print(f"Nenhum video encontrado em {canal_url}")
        return

    processados = _processar_lista_canal(
        manifesto,
        video_urls,
        lambda _manifesto, _video_id, _video: True,
    )

    reconstruir_indice_busca()
    print(f"Videos processados: {processados}")
    print(f"Total de videos cadastrados: {manifesto['videos']}")


def catalogar_delta(canal_url=URL_DO_CANAL):
    manifesto = garantir_estrutura()
    ids_catalogados = {item["id"] for item in manifesto["itens"]}

    video_urls = listar_videos_canal(canal_url)
    if not video_urls:
        print(f"Nenhum video encontrado em {canal_url}")
        return

    novos = [video for video in video_urls if extrair_video_id(normalizar_url(video["url"])) not in ids_catalogados]
    print(f"Videos novos para indexar: {len(novos)}")

    if not novos:
        print("Nenhum video novo encontrado.")
        return

    processados = _processar_lista_canal(
        manifesto,
        novos,
        lambda _manifesto, _video_id, _video: True,
    )

    print(f"Videos novos processados: {processados}")
    print(f"Total de videos cadastrados: {manifesto['videos']}")


def reprocessar_sem_transcricao():
    manifesto = garantir_estrutura()
    pendentes = [item for item in manifesto["itens"] if not item.get("possui_transcricao")]

    if not pendentes:
        print("Nenhum video pendente de transcricao.")
        return

    print(f"Reprocessando {len(pendentes)} videos sem transcricao...")
    recuperados = 0

    for indice, item in enumerate(pendentes, start=1):
        print("-" * 20)
        print(f"Reprocessando {indice}/{len(pendentes)}: {item['titulo']}")

        video_url = normalizar_url(item["url"])
        if processar_transcricao_video(manifesto, video_id=item["id"], video_url=video_url, titulo=item["titulo"]):
            recuperados += 1

    print(f"Transcricoes recuperadas: {recuperados}/{len(pendentes)}")
    print(f"Total de videos cadastrados: {manifesto['videos']}")


def main():
    parser = argparse.ArgumentParser(description="Catalogacao e transcricao de videos do YouTube")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--reprocessar-tudo",
        action="store_true",
        help="Apaga todo o banco e reindexa todos os videos do canal",
    )
    grupo.add_argument(
        "--delta",
        action="store_true",
        help="Indexa apenas videos novos ainda nao catalogados",
    )
    grupo.add_argument(
        "--reprocessar-sem-transcricao",
        action="store_true",
        help="Tenta obter transcricao para videos marcados sem transcricao",
    )
    parser.add_argument(
        "--canal",
        default=URL_DO_CANAL,
        help=f"URL do canal ou playlist (padrao: {URL_DO_CANAL})",
    )
    args = parser.parse_args()

    if args.reprocessar_tudo:
        reprocessar_tudo(args.canal)
    elif args.delta:
        catalogar_delta(args.canal)
    elif args.reprocessar_sem_transcricao:
        reprocessar_sem_transcricao()


if __name__ == "__main__":
    main()
