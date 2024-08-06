import os
import time
import psycopg2  # Импортируем psycopg2 для работы с PostgreSQL
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

# Подключаемся к базе данных PostgreSQL
conn = psycopg2.connect(
    dbname="cardglot-beta",
    user="postgres",
    password="postgres",
    host="194.87.219.18",
    port="5432"
)

with conn:
    cursor = conn.cursor()

    # Проверяем, существует ли столбец "definition"
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='Translator_translations' AND column_name='definition';
    """)
    columns = cursor.fetchall()


    # Получаем слова, для которых определение еще не запрашивалось
    cursor.execute('SELECT word FROM "Translator_translations" WHERE definition like %s', ('%/ˈdʒʌŋk fuːd/%',))
    english_words = cursor.fetchall()

    # Обрабатываем слова
    for word in english_words:
        word = word[0]
        print(word)
        output = word

        word1 = word
        if ' ' in word:
            word1 = word.replace(' ', '-') + f"?q={word.replace(' ', '+')}"

        url = "https://www.oxfordlearnersdictionaries.com/definition/english/" + str(word1).lower()
        response = requests.get(url, headers=headers)

        if response.status_code == 404:
            print(f'Слово "{word}" не найдено\n')
            cursor.execute('''
                UPDATE "Translator_translations"
                SET definition = '-'
                WHERE word = %s 
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
            UPDATE "Translator_translations" 
            SET definition = %s
            WHERE word = %s
        ''', (output_text, word))

        # Задержка между запросами для предотвращения блокировки (если требуется)
        delay = random.uniform(1, 3)
        time.sleep(delay)

        print('---------')
        conn.commit()

    cursor.close()
