import logging
import os
import sys
import time

import requests
from requests.exceptions import RequestException
from telegram import Bot
from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import (ResponseError, StatusCodeError, TokenError)

logger = logging.getLogger(__name__)

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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Отправлено сообщение в Telegram: {message}')
    except Exception:
        logger.error('Сбой отправки сообщения в Telegram!')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except RequestException as error:
        logger.error(f'Сервер yandex.practicum вернул ошибку: {error}')
        raise ConnectionError(f'Ошибка подключения к API: {error}')
    status_code = response.status_code
    if status_code != HTTPStatus.OK:
        logger.error(f'Ошибка при запросе к API, код: {status_code}')
        raise StatusCodeError(f'Ошибка при запросе к API, код: {status_code}')
    try:
        response_json = response.json()
    except Exception as error:
        logger.error('Ответ от сервера должен быть в формате JSON')
        raise ResponseError(f'Отказ работы сервера. Ошибка: {error}')
    return response_json


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем!')
        raise TypeError('Ответ API не является словарем!')
    if 'homeworks' not in response:
        logger.error('Отсутствует ключ "homeworks!"')
        raise KeyError('Отсутствует ключ "homeworks!"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error(
            'Домашние задания оформлены не как список c ключом "homeworks"!'
        )
        raise TypeError(
            'Домашние задания оформлены не как список c ключом "homeworks"!'
        )
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'status' not in homework:
        logger.error(
            'Отсутствует ключ "homework_name" в статусах работы'
        )
        raise KeyError(
            'Отсутствует ключ "homework_name" в статусах работы'
        )
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in VERDICTS:
        logger.error(
            f'Отсутствует ключ "{homework_status}" в статусах работы'
        )
        raise KeyError(
            f'Отсутствует ключ "{homework_status}" в статусах работы'
        )
    verdict = VERDICTS[homework_status]
    if not verdict:
        raise logger.error('Отсутствие ожидаемых ключей в ответе API.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов."""
    flag = True
    for name in TOKENS:
        if globals()[name] is None:
            logger.critical(f'Токен {name} не найден!')
            flag = False
    return flag


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise TokenError('Ошибка в токенах!')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - 2000000
    last_error = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            else:
                logger.info('Домашние задания не найдены.')
            current_timestamp = response.get(
                'current_date',
                current_timestamp
            )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            try:
                if last_error != message:
                    send_message(TELEGRAM_CHAT_ID, message)
            except Exception as error:
                logger.error(f'Сбой отправки сообщения: {error}')
                last_error = message
        finally:
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
    logger = logging.getLogger(__name__)
    try:
        main()
    except KeyboardInterrupt:
        logger.critical('Выход из программы по Ctrl-C')
        sys.exit(0)
