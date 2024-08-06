
import asyncio
import aiohttp
import os
import asyncpg
from bs4 import BeautifulSoup
from asyncio import Queue, Semaphore

MAX_CONCURRENT_TASKS = 100
AUDIO_DIR = "audio_files"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

db_config = {
    "user": "tuz1",
    "password": "1234tuz1",
    "database": "cardglot-beta",
    "host": "194.87.219.18",
    "port": "5432"
}


async def add_data_to_base(word, mp3_links):
    try:
        conn = await asyncpg.connect(**db_config)
        await conn.execute('''
            UPDATE "Translator_translations"
            SET us_audio = $1, gb_audio = $2
            WHERE word = $3
        ''', mp3_links.get('us_audio', '-'), mp3_links.get('gb_audio', '-'), word)
        await conn.close()
        print(f"Updated: {word}")
    except Exception as e:
        print(f"Error updating database for word {word}: {e}")


async def download_audio(url, file_path):
    try:
        print(f"Downloading {file_path}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    f.write(await response.read())
        print(f"Successfully downloaded {file_path}")
    except Exception as e:
        print(f"Error downloading {file_path}: {e}")


async def get_first_mp3_links(page_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(page_url, headers=headers) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), 'html.parser')

                sound_elements_us = soup.find_all('div', class_='sound audio_play_button pron-us icon-audio')
                sound_elements_gb = soup.find_all('div', class_='sound audio_play_button pron-uk icon-audio')

                mp3_links = {
                    'us_audio': None,
                    'gb_audio': None
                }

                for element in sound_elements_us:
                    mp3_url = element.get('data-src-mp3')
                    if mp3_url and mp3_links['us_audio'] is None:
                        mp3_links['us_audio'] = mp3_url

                for element in sound_elements_gb:
                    mp3_url = element.get('data-src-mp3')
                    if mp3_url and mp3_links['gb_audio'] is None:
                        mp3_links['gb_audio'] = mp3_url

                return {k: v for k, v in mp3_links.items() if v is not None}
    except Exception as e:
        print(f"Error fetching page: {e}")
        return {}


async def process_word(word, conn):
    word1 = word.replace(' ', '-') + f"?q={word.replace(' ', '+')}" if ' ' in word else word
    url = f"https://www.oxfordlearnersdictionaries.com/definition/english/{word1.lower()}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=60) as response:
                if response.status == 404:
                    mp3_links = {'us_audio': "-", 'gb_audio': "-"}
                    await add_data_to_base(word, mp3_links)
                    print(f'Word "{word}" not found\n')
                    return

                mp3_links = await get_first_mp3_links(url)
                if mp3_links:
                    await add_data_to_base(word, mp3_links)
                    for accent, link in mp3_links.items():
                        file_path = os.path.join(AUDIO_DIR, f"{word}_{accent}.mp3")
                        await download_audio(link, file_path)
                        print(f"{accent} : {word} ({link})")
                else:
                    print("Failed to find audio links.")
    except Exception as e:
        print(f"Error processing word {word}: {e}")


async def process_words(queue, conn, semaphore):
    while not queue.empty():
        word = await queue.get()
        async with semaphore:
            await process_word(word, conn)
        queue.task_done()


async def main():
    conn = None
    try:
        conn = await asyncpg.connect(**db_config)
        records = await conn.fetch(
            'SELECT word FROM "Translator_translations" where us_audio is null')

        queue = Queue()
        for record in records:
            await queue.put(record['word'])

        semaphore = Semaphore(MAX_CONCURRENT_TASKS)
        tasks = [process_words(queue, conn, semaphore) for _ in range(MAX_CONCURRENT_TASKS)]

        await asyncio.gather(*tasks)
    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
