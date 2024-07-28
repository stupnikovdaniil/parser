
import os
import time
import sqlite3
import requests
from bs4 import BeautifulSoup
import random

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36 OPR/40.0.2308.81',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'DNT': '1',
    'Accept-Encoding': 'gzip, deflate, lzma, sdch',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'
}

db_path = 'database.sqlite3'

with sqlite3.connect(db_path) as conn:
    # Проверяем, существует ли столбец
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(translations);")
    columns = cursor.fetchall()



    # Получаем слова для которых определение еще не запрашивалось
    cursor.execute("SELECT word FROM Translator_translations WHERE definition is null")
    english_words = cursor.fetchall()

    # Обрабатываем слова
    for word in english_words:
        word = word[0]
        print(word)
        output = word

        output = word
        word1 = word
        if ' ' in word:
            word1 = word.replace(' ', '-') + f"?q={word.replace(' ', '+')}"

        url = "https://www.oxfordlearnersdictionaries.com/definition/english/" + str(word1).lower()
        response = requests.get(url, headers=headers)

        if response.status_code == 404:
            print(f'Слово "{word}" не найдено\n')
            conn.execute('''
                UPDATE Translator_translations
                SET definition = '-'
                WHERE word = ? 
            ''', (word,))
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        word_title = soup.find('h2', {'class': 'shcut'})
        output_text = ""

        try:
            output_text += soup.find('span', class_='pos').text.strip() + '\n'
            output_text += soup.find('span', class_='phon').text.strip() + '\n'
        except AttributeError:
            pass

        definitions = soup.find_all('li', {'class': 'sense'})
        for index, definition in enumerate(definitions, start=1):
            cefr = definition.get('cefr', '')

            definition_element = definition.find('span', {'class': 'def'})
            if definition_element:
                definition_text = definition_element.text.strip()
                output_text += f"\n{cefr} {definition_text}\n"

                examples = definition.find_all('span', {'class': 'x'})
                for example in examples:
                    output_text += f"  - {example.text.strip()}\n"
            else:
                print(f"Не удалось найти элемент <span class='def'> для слова: {word}")
                continue

        # Используйте параметризованный запрос для предотвращения SQL-инъекций
        cursor.execute('''
                        UPDATE Translator_translations 
                        SET definition = ?
                        WHERE word = ?
                    ''', (output_text, word))
        # delay = random.uniform(1, 3)
        # time.sleep(delay)
        print('---------')
        conn.commit()

    # Применяем изменения к базе данных
    conn.commit()
