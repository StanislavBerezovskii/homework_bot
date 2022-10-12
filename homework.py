import logging
import os
import time

import requests
from requests.exceptions import RequestException

from exceptions import (ResponseError, StatusCodeError, TokenError)

from telegram import Bot
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

def send_message(bot, message):
    """Отправка сообщения об изменении статуса."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.info(f'Отправлено сообщение: {message}')

def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except RequestException as error:
        raise ConnectionError(f'Ошибка подключения к API: {error}')
    status_code = response.status_code
    if status_code != 200:
        raise StatusCodeError(f'Ошибка при запросе к API, код статуса: {status_code}')
    response_json = response.json()
    for key in ('error'):
        if key in response_json:
            raise ResponseError(f'Отказ обслуживания. Ошибка: {key}')
    return response_json

def check_response(response):
    """Проверка ответа API."""
    if type(response) is not dict:
        raise TypeError('Ответ API не является словарем!')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks!"')
    homeworks = response['homeworks']
    if type(homeworks) is not list:
        raise TypeError('Домашние задания оформлены не как список под ключом "homeworks"!')
    return response.get('homeworks')

def parse_status(homework):
    """Извлечение из информации о домашней работе статуса этой работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ "homework_name"!')
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'

def check_tokens():
    """Проверка наличия токенов."""
    flag = True
    for name in TOKENS:
        if globals()[name] is None:
            logging.critical(f'Токен {name} не найден!')
            flag = False
    return flag

updater = Updater(token=TELEGRAM_TOKEN)

def say_hello(update, context):
    chat = update.effective_chat
    context.bot.send_message(
        chat_id=chat.id, 
        text='Приветствую, я бот-ассистент! Давайте проверим статус ваших домашних заданий.'
    )

def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise TokenError('Ошибка в токенах!')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            current_timestamp = response.get('current_date', current_timestamp)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            try:
                bot.send_message(TELEGRAM_CHAT_ID, message)
            except Exception as error:
                logging.exception(f'Ошибка при отправке сообщения: {error}')
        time.sleep(RETRY_TIME)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(__file__ + '.log', encoding='UTF-8')],
        format=(
            '%(asctime)s, %(levelname)s, %(funcName)s, %(lineno)d, %(message)s'
        ))
    updater.dispatcher.add_handler(CommandHandler('start', say_hello))
    updater.start_polling(poll_interval=600.0)
    updater.idle()
    main()
