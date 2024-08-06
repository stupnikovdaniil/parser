import sqlite3
import xml.etree.ElementTree as ET
import re

def extract_words_from_fb2(file_path):
    # Открываем файл в формате FB2
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Список для хранения всех слов
    words = set()

    # Регулярное выражение для разделения текста на слова
    word_pattern = re.compile(r'\b[A-Za-z]+\b')

    # Парсим все <p> элементы, содержащие текст
    for paragraph in root.iter('{http://www.gribuser.ru/xml/fictionbook/2.0}p'):
        # Получаем текст абзаца
        text = paragraph.text
        if text:
            # Используем регулярное выражение для разделения текста на слова
            words.update(word_pattern.findall(text.lower()))  # Преобразуем слова к нижнему регистру и добавляем в множество

    return words  # Возвращаем множество уникальных слов

# Укажите путь к файлу FB2
fb2_file_path = 'Wallace David. Infinite jest - royallib.com.fb2'

# Извлекаем уникальные слова из книги
unique_words_from_book = extract_words_from_fb2(fb2_file_path)

# Подключаемся к базе данных
conn = sqlite3.connect('database.sqlite3')

try:
    cursor = conn.cursor()



    # Получаем слова из столбца translation
    cursor.execute("SELECT DISTINCT word FROM Translator_translations")
    words_from_translation_column = set(word[0] for word in cursor.fetchall() if word[0])

    # Вычитаем слова из translation из слов книги
    unique_words = unique_words_from_book - words_from_translation_column

    # Вставка данных в базу данных
    cursor.executemany("INSERT INTO Translator_translations (word) VALUES (?)", [(word,) for word in unique_words])


    # Сохранение изменений
    conn.commit()

    # Вывод информации о добавленных словах
    for word in unique_words:
        print(f"Слово '{word}' добавлено в базу данных")

except sqlite3.Error as e:
    print("Ошибка при работе с SQLite:", e)

finally:
    # Закрываем соединение
    conn.close()
