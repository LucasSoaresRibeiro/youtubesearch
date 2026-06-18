import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from storage import buscar_video_cadastrado, extrair_video_id, garantir_estrutura, registrar_video

REPROCESSAR_TRANSCRICOES_VAZIAS = False
IDIOMAS_PREFERIDOS = ["pt", "pt-BR", "pt-PT"]

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


def buscar_transcricao(video_url):
    video_id = extrair_video_id(video_url)
    if not video_id:
        raise ValueError(f"Nao foi possivel extrair o ID do video: {video_url}")

    transcript = _transcript_api.fetch(video_id, languages=IDIOMAS_PREFERIDOS)
    return [
        {
            "tStartMs": int(snippet.start * 1000),
            "text": limpar_texto(snippet.text),
        }
        for snippet in transcript
        if limpar_texto(snippet.text)
    ]


def criar_item_video(video_id, video_url, titulo, transcricao):
    return {
        "id": video_id,
        "url": video_url,
        "titulo": titulo,
        "possui_transcricao": len(transcricao) > 0,
        "transcricao": transcricao,
    }


def page_down(driver):
    for _ in range(1, 40):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        time.sleep(1)


def obter_transcricoes(canal_url):
    manifesto = garantir_estrutura()

    driver = webdriver.Chrome()
    driver.get(canal_url)

    time.sleep(2)
    page_down(driver)

    videos = driver.find_elements(By.CSS_SELECTOR, "a#video-title-link")
    video_urls = []
    for video in videos:
        try:
            video_urls.append(
                {
                    "titulo": video.get_attribute("title"),
                    "url": video.get_attribute("href"),
                }
            )
        except Exception as e:
            print(e)

    driver.quit()

    counter = 0
    for video_url_obj in video_urls:
        counter += 1
        print("-" * 20)
        print(f"Processando {counter}/{len(video_urls)} ...")

        video_url = normalizar_url(video_url_obj["url"])
        video_id = extrair_video_id(video_url)
        if not video_id:
            print(f"URL invalida: {video_url}")
            continue

        video_cadastrado = buscar_video_cadastrado(manifesto, video_id)
        if video_cadastrado and len(video_cadastrado.get("transcricao", [])) > 0:
            if not REPROCESSAR_TRANSCRICOES_VAZIAS:
                print(f"Ignorando video cadastrado com transcricao: {video_url_obj['titulo']}")
                continue

        try:
            transcricao = buscar_transcricao(video_url)
            video_item = criar_item_video(video_id, video_url, video_url_obj["titulo"], transcricao)
            registrar_video(manifesto, video_item)
            print(f"Transcricao obtida: {len(transcricao)} segmentos (salvo em data/videos/{video_id}.json)")

        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
            print(f"Sem transcricao para {video_url}: {e}")
            if not video_cadastrado:
                registrar_video(
                    manifesto,
                    criar_item_video(video_id, video_url, video_url_obj["titulo"], []),
                )

        except CouldNotRetrieveTranscript as e:
            print(f"Erro ao obter a transcricao do video {video_url}: {e}")
            if not video_cadastrado:
                registrar_video(
                    manifesto,
                    criar_item_video(video_id, video_url, video_url_obj["titulo"], []),
                )

        except Exception as e:
            print(f"Erro inesperado ao obter a transcricao do video {video_url}: {e}")

    print(f"Total de transcricoes cadastradas: {manifesto['videos']}")


URL_DO_CANAL = "https://www.youtube.com/@IBMaranata/streams"

if __name__ == "__main__":
    obter_transcricoes(URL_DO_CANAL)
