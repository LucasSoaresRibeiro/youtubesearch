from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time
from datetime import datetime

def save(transcricoes):
    print('Atualizando base...')

    with open('transcricoes.json', 'w', encoding='utf-8') as f:
        json.dump(transcricoes, f, ensure_ascii=False, indent=4)

    with open('info.json', 'w', encoding='utf-8') as f:
        info = {
            'videos': len(transcricoes),
            'dataExecucao': datetime.today().strftime('%d/%m/%Y')
        }
        json.dump(info, f, ensure_ascii=False, indent=4)

def page_down(driver):
    for attempt in range(1, 40):
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
    with open('transcricoes.json', encoding='utf-8') as fh:
        transcricoes = json.load(fh)

    time.sleep(2)

    page_down(driver)

    # Navegar pelos vídeos do canal
    videos = driver.find_elements(By.CSS_SELECTOR, 'a#video-title-link')
    video_urls = []
    for video in videos:
        try:
            # video_urls.append(video.get_attribute('href'))
            video_urls.append({
                'titulo': video.get_attribute('title'),
                'url': video.get_attribute('href')
            })

        except Exception as e:
            print(e)

    counter = 0
    for video_url_obj in video_urls:
        
        counter += 1
        print('-'*20)
        print(f'Processando {counter}/{len(video_urls)} ...')
        # print(f'Parcial de transcricoes cadastradas: {len(transcricoes)}')

        video_url = video_url_obj['url']
        
        if video_url in [tr['url'] for tr in transcricoes]:
            print(f"Ignorando video cadastrado: {video_url_obj['titulo']}")
            continue

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
                'titulo': video_url_obj['titulo'],
                'possui_transcricao': True,
                'transcricao': transcricao
            })

            if len(transcricoes) % 30 == 0:
                save(transcricoes)

        except Exception as e:
            # print(f'Erro ao obter a transcrição do vídeo {video_url}: {e}')
            print(f'Erro ao obter a transcrição do vídeo {video_url}')

            transcricoes.append({
                'url': video_url,
                'titulo': video_url_obj['titulo'],
                'possui_transcricao': False,
                'transcricao': []
            })

            if len(transcricoes) % 30 == 0:
                save(transcricoes)

    save(transcricoes)

    driver.quit()

    print(f'Total de transcrições cadastradas: {len(transcricoes)}')

# Exemplo de uso
URL_DO_CANAL = 'https://www.youtube.com/@IBMaranata/streams'
obter_transcricoes(URL_DO_CANAL)

























