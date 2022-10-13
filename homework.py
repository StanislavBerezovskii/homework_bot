import logging
import os
import time

import requests
from requests.exceptions import RequestException
from telegram import Bot
from dotenv import load_dotenv

from exceptions import (ResponseError, StatusCodeError, TokenError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

VERDICTS = {
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
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except RequestException as error:
        raise ConnectionError(f'Ошибка подключения к API: {error}')
    status_code = response.status_code
    if status_code != 200:
        raise StatusCodeError(f'Ошибка при запросе к API, код: {status_code}')
    try:
        response_json = response.json()
    except Exception as error:
        raise ResponseError(f'Отказ обслуживания. Ошибка: {error}')
    return response_json


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем!')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks!"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'Домашние задания оформлены не как список c ключом "homeworks"!'
        )
    return response.get('homeworks')


def parse_status(homework):
    """Извлечение из информации о домашней работе статуса этой работы."""
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ "homework_name"!')
    homework_name = homework['homework_name']
    if 'homework_status' not in VERDICTS:
        raise ValueError(f'Неизвестный статус: {homework_status}')
    homework_status = homework['status']
    verdict = VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов."""
    flag = True
    for name in TOKENS:
        if globals()[name] is None:
            logging.critical(f'Токен {name} не найден!')
            flag = False
    return flag


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
                send_message(TELEGRAM_CHAT_ID, message)
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
    main()
