from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time

def page_down(driver):
    for attempt in range(1, 20):
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
        time.sleep(1)

def obter_transcricoes(canal_url):
    # Configuração do Selenium WebDriver
    driver = webdriver.Chrome()  # Certifique-se de ter o chromedriver instalado e no PATH
    driver.get(canal_url)

    # Lista para armazenar as transcrições
    transcricoes = []
    
    # Salva as transcrições em um arquivo JSON
    with open('transcricoes.json', 'w', encoding='utf-8') as f:
        json.dump(transcricoes, f, ensure_ascii=False, indent=4)

    time.sleep(2)

    page_down(driver)

    # Navegar pelos vídeos do canal
    videos = driver.find_elements(By.CSS_SELECTOR, 'a#video-title-link')
    video_urls = []
    for video in videos:
        try:
            video_urls.append(video.get_attribute('href'))
            # driver.find_element(By.CSS_SELECTOR, 'button#button[aria-label="Carregar mais"]')
            # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # break

        except Exception as e:
            print(e)

    for video_url in video_urls:
        driver.get(video_url)
        try:
            # Espera até que as legendas estejam disponíveis
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button.ytp-subtitles-button'))
            )
            # Ativa as legendas
            driver.find_element(By.CSS_SELECTOR, 'button.ytp-subtitles-button').click()
            time.sleep(2)  # Espera um pouco para garantir que as legendas sejam carregadas

            # Executa a função JavaScript para obter a transcrição
            script = """
            async function getSubs(langCode = 'pt') {
                let ct = JSON.parse((await (await fetch(window.location.href)).text()).split('ytInitialPlayerResponse = ')[1].split(';var')[0]).captions.playerCaptionsTracklistRenderer.captionTracks, findCaptionUrl = x => ct.find(y => y.vssId.indexOf(x) === 0)?.baseUrl, firstChoice = findCaptionUrl("." + langCode), url = firstChoice ? firstChoice + "&fmt=json3" : (findCaptionUrl(".") || findCaptionUrl("a." + langCode) || ct[0].baseUrl) + "&fmt=json3&tlang=" + langCode;
                return (await (await fetch(url)).json()).events.map(x => ({...x, text: x.segs?.map(x => x.utf8)?.join(" ")?.replace(/\\n/g,' ')?.replace(/♪|'|"|\\.{2,}|<[^>]*>|{[^}]*}|\\[[^\\]]*\\]/g,'')?.trim() || ''}));
            }
            async function logSubs(langCode) {
                const subs = await getSubs(langCode);
                const text = subs.map(x => (
                    {
                        tStartMs: x.tStartMs,
                        text: x.text
                    }
                ));
                return text;
            }
            return await logSubs('pt');
            """
            transcricao = driver.execute_script(script)
            transcricoes.append({
                'url': video_url,
                'titulo': driver.execute_script("return document.title"),
                'transcricao': transcricao
            })

            # Salva as transcrições em um arquivo JSON
            with open('transcricoes.json', 'w', encoding='utf-8') as f:
                json.dump(transcricoes, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f'Erro ao obter a transcrição do vídeo {video_url}: {e}')
        # finally:
        #     driver.back()

    driver.quit()

# Exemplo de uso
URL_DO_CANAL = 'https://www.youtube.com/@IBMaranata/streams'
obter_transcricoes(URL_DO_CANAL)

























