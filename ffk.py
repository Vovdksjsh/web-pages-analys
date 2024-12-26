import requests  # Для загрузки содержимого веб-страниц
from bs4 import BeautifulSoup  # Для извлечения текста из HTML
import hashlib  # Для создания хэша содержимого
import pymysql  # Для работы с базой данных MySQL
import difflib  # Для анализа изменений в содержимом страниц
import threading  # Для многопоточности (чтобы мониторинг не блокировал интерфейс)
import tkinter as tk  # Для создания графического интерфейса
from tkinter import messagebox  # Для вывода сообщений пользователю
import time  # Для реализации задержек в цикле мониторинга

# Глобальная переменная для управления состоянием мониторинга
monitoring_active = False

# Подключение к базе данных MySQL
def get_db_connection():
    return pymysql.connect(
        host="localhost",  # Адрес сервера MySQL
        user="root",  # Имя пользователя базы данных
        password="Qwerty123",  # Пароль пользователя
        database="five"  # Название базы данных
    )

# Инициализация базы данных
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            url VARCHAR(255) PRIMARY KEY,  -- URL как уникальный идентификатор
            hash VARCHAR(32),             -- MD5-хэш содержимого страницы
            content TEXT                  -- Текстовое содержимое страницы
        )
    """)
    conn.commit()
    conn.close()

# Получение текстового содержимого страницы
def fetch_page(url):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text(separator="\n", strip=True)

# Сравнение содержимого страниц
def compare_content(old_content, new_content):
    diff = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        lineterm="",
        n=0)
    return [line for line in diff if line.startswith(('+', '-'))]

# Обновление данных страницы
def update_page(url, content, output_widget):
    hash_value = hashlib.md5(content.encode('utf-8')).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT hash, content FROM pages WHERE url = %s", (url,))
    result = cursor.fetchone()

    if result:
        old_hash, old_content = result
        if old_hash != hash_value:
            output_widget.insert(tk.END, f"[ИЗМЕНЕНИЕ] На странице {url} обнаружены изменения:\n")
            diff = compare_content(old_content, content)
            for line in diff:
                output_widget.insert(tk.END, f"{line}\n")
            cursor.execute(
                "UPDATE pages SET hash = %s, content = %s WHERE url = %s",
                (hash_value, content, url)
            )
        else:
            output_widget.insert(tk.END, f"[БЕЗ ИЗМЕНЕНИЙ] Страница {url} не изменилась.\n")
    else:
        output_widget.insert(tk.END, f"[НОВАЯ СТРАНИЦА] Добавление страницы {url}.\n")
        cursor.execute(
            "INSERT INTO pages (url, hash, content) VALUES (%s, %s, %s)",
            (url, hash_value, content))
    conn.commit()
    conn.close()

# Основной процесс мониторинга
def monitor_pages(output_widget, interval):

    global monitoring_active
    monitoring_active = True

    while monitoring_active:
        urls = get_urls()
        for url in urls:
            if not monitoring_active:
                break
            try:
                content = fetch_page(url)
                update_page(url, content, output_widget)
            except Exception as e:
                output_widget.insert(tk.END, f"[ОШИБКА] Ошибка при обработке {url}: {e}\n")
        if not monitoring_active:
            break

        output_widget.insert(tk.END, f"[ИНФО] Ожидание {interval} секунд перед следующей проверкой...\n")
        output_widget.update()
        time.sleep(interval)

    output_widget.insert(tk.END, "[ИНФО] Мониторинг завершен.\n")
    output_widget.update()

# Остановка мониторинга
def stop_monitoring(output_widget):

    global monitoring_active
    monitoring_active = False
    output_widget.insert(tk.END, "[ИНФО] Мониторинг остановлен.\n")

# Получение списка URL из базы
def get_urls():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM pages")
    urls = [row[0] for row in cursor.fetchall()]
    conn.close()
    return urls

# Удаление URL из базы данных
def delete_url(url, output_widget):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pages WHERE url = %s", (url,))
    conn.commit()
    conn.close()
    output_widget.insert(tk.END, f"[УДАЛЕНО] URL {url} удалён из базы данных.\n")

# Очистка базы данных
def clear_database(output_widget):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE pages")
    conn.commit()
    conn.close()
    output_widget.insert(tk.END, "[ИНФО] Таблица с сайтами полностью очищена.\n")

# Графический интерфейс
def create_gui():

    def add_url():
        url = url_entry.get()
        if not url:
            messagebox.showerror("Ошибка", "URL не может быть пустым!")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO pages (url, hash, content) VALUES (%s, %s, %s)", (url, "", ""))
            conn.commit()
            conn.close()
            output.insert(tk.END, f"[ДОБАВЛЕНО] URL {url} добавлен для отслеживания.\n")
        except pymysql.connect.Error as e:
            output.insert(tk.END, f"[ОШИБКА] Не удалось добавить URL {url}: {e}\n")

    def remove_url():
        url = url_entry.get()
        if not url:
            messagebox.showerror("Ошибка", "URL не может быть пустым!")
            return

        try:
            delete_url(url, output)
        except Exception as e:
            output.insert(tk.END, f"[ОШИБКА] Не удалось удалить URL {url}: {e}\n")

    def start():
        try:
            interval = int(interval_entry.get())
            thread = threading.Thread(target=monitor_pages, args=(output, interval), daemon=True)
            thread.start()
        except ValueError:
            messagebox.showerror("Ошибка", "Интервал должен быть числом!")

    def stop():
        stop_monitoring(output)

    def clear_db():
        clear_database(output)

    # Настройка окна приложения
    root = tk.Tk()
    root.title("Анализатор изменений веб-страниц")

    # Поле ввода URL
    tk.Label(root, text="URL:").grid(row=0, column=0, sticky="w")
    url_entry = tk.Entry(root, width=50)
    url_entry.grid(row=0, column=1, padx=5, pady=5)

    # Поле ввода интервала
    tk.Label(root, text="Интервал (сек):").grid(row=1, column=0, sticky="w")
    interval_entry = tk.Entry(root, width=10)
    interval_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

    # Кнопки управления
    tk.Button(root, text="Добавить URL", command=add_url).grid(row=0, column=2, padx=5, pady=5)
    tk.Button(root, text="Удалить URL", command=remove_url).grid(row=0, column=3, padx=5, pady=5)
    tk.Button(root, text="Запустить мониторинг", command=start).grid(row=1, column=2, padx=5, pady=5)
    tk.Button(root, text="Остановить", command=stop).grid(row=1, column=3, padx=5, pady=5)
    tk.Button(root, text="Очистить БД", command=clear_db).grid(row=2, column=2, columnspan=2, padx=5, pady=5)

    # Поле вывода информации
    output = tk.Text(root, width=80, height=20)
    output.grid(row=3, column=0, columnspan=4, padx=5, pady=5)

    root.mainloop()

# Запуск программы
if __name__ == "__main__":
    init_db()
    create_gui()
