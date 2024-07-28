import asyncio
import re
from bs4 import BeautifulSoup
from collections import defaultdict
from asyncio import Queue, Semaphore, sleep
from bs4 import BeautifulSoup
from aiosqlite import connect
from playwright.async_api import async_playwright

db_path = 'database.sqlite3'
MAX_CONCURRENT_TASKS = 7


async def process_word(word, conn):
    all_sentences = []  # Создаем пустой список для хранения всех предложений
    words = []

    async with async_playwright() as p:
        browser = await p.webkit.launch()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print(f"Processing word: {word}")

            url = f"https://translate.yandex.ru/?source_lang=en&target_lang=ru&text={word}"

            await page.goto(url)
            await page.wait_for_load_state('load')
            await page.wait_for_timeout(3000)

            # Get the HTML content from the page
            html_content = await page.content()

            soup = BeautifulSoup(html_content, 'html.parser')

            # ------------------------------------------------translation start-----------------------------------------------------------------------

            def is_english_word(word):
                # Проверяем, содержит ли слово только буквы английского алфавита (без учета регистра)
                return re.match("^[а-яА-Я]+$", word.lower()) is not None

            # ------------------------------------------------translation end---------------------------------------------------------------------

            # ------------------------------------------------sinonims_start-----------------------------------------------------------------------
            list_items = ""  # Initialize list_items outside the try block

            try:
                list_items = soup.find('ul', class_='ZaWGSXW_2HvMaxnFAcyY').find_all('li')
            except AttributeError:
                print("error")

            # Извлечение текста из каждого элемента списка
            sinonims = [item.text.strip() for item in list_items]
            # Вывод нужных слов
            sinonim = ', '.join(sinonims)
            sinonim = sinonim.replace(', ...', '')
            print(sinonim)

            # ------------------------------------------------sinonims_end-----------------------------------------------------------------------

            #------------------------------------------------yand_example_start-----------------------------------------------------------------------
            try:
                word_elements = soup.find_all('span', class_=['gwLE_B_fhZwoA9WSW_oe', 'HqnOQu_XPJFkULxccxrt'])
                if not word_elements:
                    word_elements = ''
            except AttributeError:
                print("error")

            for word_element in word_elements:
                word_text = word_element.text.strip()  # Извлечение текста и удаление лишних пробелов
                if word_text not in words:  # Проверка на дубли
                    words.append(word_text)  # Добавление слова в список

            english_words = [word for word in words if is_english_word(word)]
            translation = ', '.join(english_words)

            example_groups = soup.find_all('div', class_='hrY5mhJVXyHzSbhkUOJg')
            for example_group in example_groups:
                # Extract English text
                english_text_element = example_group.select_one('.LgQod4Ha6AzTyunhk52j')
                # Extract Russian text
                russian_text_element = example_group.select_one('.rHurNUWA57R5EBjzibOQ')

                if english_text_element and russian_text_element:
                    english_text = english_text_element.text.strip()
                    russian_text = russian_text_element.text.strip()

                    # Replace words in English and Russian text
                    for w in words:
                        english_text = english_text.replace(w, f'<span style="background-color: orange;">{w}</span>')
                        russian_text = russian_text.replace(w, f'<span style="background-color: yellow;">{w}</span>')

                    all_sentences.append((english_text, russian_text))  # Append to all_sentences

            combined_sentences = ""
            for english, russian in all_sentences:
                combined_sentences += f" - (En): {english}\n - (Ru): {russian}\n\n"
            # ------------------------------------------------yand_example_end-----------------------------------------------------------------------

            await save_combined_sentences_to_db(conn, word, combined_sentences, translation, sinonim)

            print(f"Successfully processed word {word}")

        except Exception as process_error:
            print(f"Error processing word {word}: {process_error}")
            # Handle the processing error
        finally:
            await browser.close()











async def process_words(queue, conn, semaphore):
    while not queue.empty():
        word = await queue.get()
        async with semaphore:
            await process_word(word, conn)  # Pass word and connection
        queue.task_done()


async def save_combined_sentences_to_db(conn, word, sinonim, translation, combined_sentences):
    try:
        await conn.execute('''
            UPDATE Translator_translations
            SET synonyms = ?,
            translation = ?,
            yand_example = ?
            WHERE word = ?
        ''', (str(combined_sentences), translation, sinonim, str(word)))
        await conn.commit()
    except Exception as db_error:
        print(f"Error updating database for word {word}: {db_error}")


async def main():
    conn = None
    try:
        conn = await connect(db_path)
        cursor = await conn.cursor()

        await cursor.execute("PRAGMA table_info(Translator_translations);")
        columns = await cursor.fetchall()

        await cursor.execute("SELECT word FROM Translator_translations where translation != '' and yand_example = ''")
        english_words = await cursor.fetchall()

        queue = asyncio.Queue()

        for word in english_words:
            await queue.put(word[0])

        semaphore = Semaphore(MAX_CONCURRENT_TASKS)
        tasks = [process_words(queue, conn, semaphore) for _ in range(len(english_words))]

        await asyncio.gather(*tasks)

    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
