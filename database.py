import sqlite3
import re
from morphological_rules import generate_explanation, remove_stress_marks  # Імпортуємо функції


conn = sqlite3.connect('morphology.db')
c = conn.cursor()

# Створення таблиць
c.execute('''CREATE TABLE IF NOT EXISTS Word (id INTEGER PRIMARY KEY, basic_word TEXT, split_word TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS Morphological_alternation (id INTEGER PRIMARY KEY, word_id INTEGER, 
                morphology_process TEXT, meaning TEXT, explanation TEXT, 
                FOREIGN KEY (word_id) REFERENCES Word(id))''')
conn.commit()

# Обробка даних з файлу
with open('words_data.txt', 'r', encoding='utf-8') as file:
    for line in file:
        line = line.strip()
        # Виділяємо основну частину слова і додаткову інформацію
        parts = re.split(r'\s*(\([^()]+(?:\([^()]+\)[^()]*)*\))', line)
        word_part = parts[0]
        additional_info = parts[1:]

        split_word = word_part  # Зберігаємо як є
        basic_word = remove_stress_marks(word_part.replace("/", ""))  # Видаляємо скісні риски

        # Вставка в таблицю Word
        c.execute('''INSERT INTO Word (basic_word, split_word) 
                     VALUES (?, ?)''', (basic_word, split_word))
        word_id = c.lastrowid

        morphology_process = ''
        meaning = ''
        explanation = ''

        # Обробка додаткової інформації
        for info in additional_info:
            if '~' in info:
                morphology_process += ' ' + info
            else:
                meaning += ' ' + info

        # Прибираємо початкові пробіли
        morphology_process = morphology_process.strip()
        meaning = meaning.strip()

        # Якщо є морфологічний процес
        if morphology_process:
            # Якщо це спеціальний випадок, де не повинно бути пояснення
            if morphology_process.strip() in {"(~сте[л'/ý])", "(~сте[л'/у])", "(~рост/ý)", "(~рост↔ти)", "(~бл/íв)", "(~н/ів)"}:
                explanation = "Морфонологічного пояснення немає."
            elif morphology_process.strip() == "(~ви́/ю)":
                explanation = (
                    "усічення дієслівного суфікса -ти- при творенні дієслівної форми доконаного виду майбутнього часу "
                    "першої особи однини за допомогою особового закінчення, яке додається до основи інфінітива.")
            elif morphology_process.strip() == "(~/о́ч/е)":
                explanation = (
                    "чергування [т] із [ч] у суфіксальній морфонемі при творенні дієслівної форми доконаного виду майбутнього часу третьої особи однини.")
            elif morphology_process.strip() == "(~ю́р[бл'/а]ть/ся)":
                explanation = (
                    "чергування [б] із [бл] у кореневій морфонемі при творенні дієслівної форми недоконаного виду теперішнього часу третьої особи множини ІІ дієвідміни.")
            elif morphology_process.strip() == "(~кýч[мл'/у])":
                explanation = (
                    "чергування [м] із [мл] у кореневій морфонемі при творенні дієслівної форми недоконаного виду "
                    "теперішнього часу першої особи однини ІІ дієвідміни.")
            elif morphology_process.strip() == "(~ломл/у)":
                explanation = (
                    "чергування [м] із [мл] у кореневій морфонемі при творенні дієслівної форми доконаного виду першої"
                    " особи однини майбутнього часу.")
            else:
                explanation = generate_explanation(split_word, basic_word)

            c.execute('''SELECT explanation FROM Morphological_alternation WHERE word_id = ? AND morphology_process = ?''',
                      (word_id, morphology_process))
            existing_explanation = c.fetchone()

            if existing_explanation:  # Якщо пояснення вже є
                # Якщо пояснення вже існує, не додаємо нове
                existing_explanation_text = existing_explanation[0]
                if explanation != existing_explanation_text:  # Якщо пояснення відрізняється, не додаємо
                    explanation = existing_explanation_text
                else:
                    explanation = existing_explanation_text

            # Вставка даних лише якщо немає пояснення для цього процесу
            c.execute('''INSERT INTO Morphological_alternation (word_id, morphology_process, explanation, meaning) 
                         VALUES (?, ?, ?, ?)''',
                      (word_id, morphology_process, explanation, meaning))

        # Якщо є тільки значення (без пояснення)
        elif meaning:
            c.execute('''INSERT INTO Morphological_alternation (word_id, morphology_process, explanation, meaning) 
                         VALUES (?, ?, ?, ?)''',
                      (word_id, '', '', meaning))  # Пояснення не додається


conn.commit()
conn.close()


# Підключення до бази даних
conn = sqlite3.connect('morphology.db')
c = conn.cursor()


def update_explanation(parsed_data, cursor):
    cursor.execute("SELECT id, morphology_process, explanation FROM Morphological_alternation")
    rows = cursor.fetchall()

    for row in rows:
        word_id = row[0]
        morphology_string = row[1]
        existing_explanation = row[2] if row[2] else ""

        # Розбиваємо процеси і пояснення на списки
        morphology_list = process_morphology(morphology_string)
        existing_explanations = existing_explanation.split('; ') if existing_explanation else []

        # Створюємо відповідність процес -> пояснення
        explanation_mapping = {}

        if len(existing_explanations) == len(morphology_list):
            explanation_mapping = dict(zip(morphology_list, existing_explanations))
        elif len(existing_explanations) == 1 and len(morphology_list) > 1:
            # Є тільки одне пояснення -> прив'язуємо до першого процесу
            explanation_mapping[morphology_list[0]] = existing_explanations[0]
            for morph in morphology_list[1:]:
                explanation_mapping[morph] = ''
        else:
            # Якщо кількість не збігається і не 1 пояснення — прив'язуємо пусті
            explanation_mapping = {morph: '' for morph in morphology_list}

        updated_explanations = []

        for morph in morphology_list:
            # Якщо пояснення вже є, використовуємо його
            if explanation_mapping.get(morph):
                updated_explanations.append(explanation_mapping[morph])
                continue

            # Якщо нема, шукаємо нове пояснення
            explanation_text = parsed_data.get(morph)
            if explanation_text:
                updated_explanations.append(explanation_text)
            else:
                # Пробуємо скорочення
                for i in range(1, len(morph)):
                    truncated_morph = morph[i:]
                    explanation_text = parsed_data.get(truncated_morph)
                    if explanation_text:
                        updated_explanations.append(explanation_text)
                        break
                else:
                    # Якщо нічого не знайдено, додаємо наступне:
                    updated_explanations.append('Морфонологічного пояснення немає.')

        # Об'єднуємо пояснення через "; "
        final_explanation = '; '.join(updated_explanations)

        # Оновлюємо рядок у базі даних
        cursor.execute(
            "UPDATE Morphological_alternation SET explanation = ? WHERE id = ?",
            (final_explanation, word_id)
        )


# Функція для обробки рядка morphology_process
def process_morphology(morphology_string):
    morphology_list = [part.strip() for part in morphology_string.split(',')]
    cleaned_list = []

    for element in morphology_list:
        cleaned_element = (element.replace('[', '').replace(']', '').replace("'", '').replace('(', '').replace(')', '').
                           replace('~', ''))
        cleaned_list.append(cleaned_element)

    return cleaned_list


# Функція для розбору текстового файлу та створення словника
def parse_rules_txt(file_path):
    result_dict = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            parts = line.strip().split('—')
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if ',' in key:
                    keys = key.split(',')
                    for k in keys:
                        result_dict[k.strip()] = value
                else:
                    result_dict[key] = value
    return result_dict


# Шлях до текстового файлу
file_path = 'rules.txt'

# Парсимо дані з текстового файлу та отримуємо словник
parsed_data = parse_rules_txt(file_path)

# Оновлюємо таблицю Morphological_alternation з використанням знайдених значень
update_explanation(parsed_data, c)

# Зберігаємо зміни та закриваємо з'єднання з базою даних
conn.commit()
conn.close()


def fetch_all_words():
    conn = sqlite3.connect('morphology.db')
    c = conn.cursor()

    # Отримати всі слова з бази даних
    c.execute("SELECT id, basic_word FROM Word")
    word_rows = c.fetchall()

    # Створити словник без наголосів
    words_dict = {word: word_id for word_id, word in word_rows}

    conn.close()
    return words_dict


def fetch_morphological_info(word, words_dict):
    # Отримати ID слова без наголосів
    word_id = words_dict.get(word)

    if word_id:
        # Підключення до бази даних
        conn = sqlite3.connect('morphology.db')
        c = conn.cursor()

        # Знайти інформацію про морфологічні чергування за ID слова
        c.execute("SELECT morphology_process, explanation, meaning FROM Morphological_alternation WHERE word_id"
                  " = ?", (word_id,))
        alternation_rows = c.fetchall()

        # Вивести інформацію
        for row in alternation_rows:
            morphology_process = row[0]
            explanation = row[1]
            meaning = row[2]

            explanations = explanation.split(';') if explanation else ["Морфонологічного пояснення немає"]

            if ',' in morphology_process:
                parts = [part.strip().strip('()') for part in morphology_process.split(',')]
                part1 = parts[0]
                part2 = parts[1] if len(parts) > 1 else ""
                part3 = parts[2] if len(parts) > 2 else ""

                explanation1 = explanations[0] if len(explanations) > 0 else "Морфонологічного пояснення немає"
                explanation2 = explanations[1] if len(explanations) > 1 else "Морфонологічного пояснення немає"
                explanation3 = explanations[2] if len(explanations) > 2 else "Морфонологічного пояснення немає"

                if part1:
                    print(f"({part1}) - {explanation1}")
                if part2:
                    print(f"({part2}) - {explanation2}")
                if part3:
                    print(f"({part3}) - {explanation3}")
            else:
                explanation_full = explanations[0] if explanations[0] else "Морфонологічного пояснення немає"
                print(f"({morphology_process}) - {explanation_full}")

            if meaning:
                print(f"Пояснювальна ремарка: {meaning}")

        conn.close()
    else:
        print("Слово не знайдено в базі даних.")


# Завантажити всі слова з бази даних та видалити наголоси
words_dict = fetch_all_words()

# Основний цикл програми
while True:
    user_input = input("Введіть слово (або напишіть 'стоп' для завершення): ").strip()
    if user_input.lower() == 'стоп':
        break
    fetch_morphological_info(user_input, words_dict)
