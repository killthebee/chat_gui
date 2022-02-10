import asyncio
import gui
import datetime
import aiofiles
import json
import logging
import time

from asyncio import TimeoutError
from async_timeout import timeout
from errors import TokenError
from anyio import create_task_group
from utils import (get_args, connect_to_chat, sanitize, save_token, is_token_file_exists, read_token_file,
                   delete_token_file)

loop = asyncio.get_event_loop()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('watchdog_logger')


async def read_history(filepath, queues):
    async with aiofiles.open(filepath, 'r') as f:
        messages = await f.readlines()
        for message in messages:
            queues['messages_queue'].put_nowait(message)


async def read_msgs(host, port, queues):
    event = gui.ReadConnectionStateChanged.INITIATED
    queues['status_update_queue'].put_nowait(event)
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
        event = gui.ReadConnectionStateChanged.ESTABLISHED
        queues['status_update_queue'].put_nowait(event)
        while True:
            data = await reader.read(100)
            queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection is alive. Source: New message in chat')
            try:
                message = f"[{datetime.datetime.now().strftime('%d.%m.%y %H:%M')}] {data.decode()}"
                queues['messages_queue'].put_nowait(message)
                queues['messages_to_save_queue'].put_nowait(message)
            except UnicodeDecodeError:
                continue
            # await asyncio.sleep(1)


async def save_messages(filepath, queue):
    while True:
        message = await queue.get()
        async with aiofiles.open(filepath, 'a') as f:
            await f.write(message)


async def send_message(writer, message):
    writer.write(f'{sanitize(message)}\n\n'.encode())
    await writer.drain()


async def register_user(host, port, path):
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
        await reader.readline()
        writer.write('\n'.encode())
        await writer.drain()
        await reader.readline()
        username = 'anonymous'
        writer.write(f'{sanitize(username)}\n'.encode())
        await writer.drain()
        response = await reader.readline()
        await save_token(json.loads(response)['account_hash'], path)


async def run_token_handler(host, port, path, token):
    if token:
        await save_token(token, path)
    while True:
        if is_token_file_exists(path):
            await asyncio.sleep(1)
            continue
        await register_user(host, port, path)


async def authenticate_token(reader, writer, token):
    writer.write(f'{sanitize(token)}\n\n'.encode())
    await writer.drain()
    for _ in range(0, 2):
        results = await reader.readline()
    return json.loads(results)


async def run_message_sender(host, port, token, queues):
    event = gui.SendingConnectionStateChanged.INITIATED
    queues['status_update_queue'].put_nowait(event)
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
        event = gui.SendingConnectionStateChanged.ESTABLISHED
        queues['status_update_queue'].put_nowait(event)
        authentication_result = await authenticate_token(reader, writer, token)
        queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection is alive. Prompt before auth')
        if not authentication_result:
            queues['error_queue'].put_nowait(['Неверный токен', 'Проверьте токен, сервер его не узнал'])
            raise TokenError('Invalid token')
        else:
            queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection is alive. Authorization done')
            event = gui.NicknameReceived(authentication_result['nickname'])
            queues['status_update_queue'].put_nowait(event)
        while True:
            message = await queues['sending_queue'].get()
            await send_message(writer, message)
            queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection is alive. Message sent')


async def watch_for_connection(queues):
    timeout_sum = 0
    while True:
        try:
            async with timeout(1):
                event = await queues['watchdog_queue'].get()
                timeout_sum = 0
                logger.info(event)

        except TimeoutError:
            if timeout_sum >= 3:
                raise ConnectionError
            timeout_sum += 1
            logger.info(f"{timeout_sum}s timeout is elapsed")


async def handle_connection(host, sending_port, token, reading_port, queues):
    while True:
        try:
            async with create_task_group() as tg:
                tg.start_soon(run_message_sender, host, sending_port, token, queues)
                tg.start_soon(read_msgs, host, reading_port, queues)
                tg.start_soon(watch_for_connection, queues)
        except ConnectionError:
            logger.info('Reconnecting to server')


async def main():
    queues = {
        'messages_queue': asyncio.Queue(),
        'sending_queue': asyncio.Queue(),
        'status_update_queue': asyncio.Queue(),
        'messages_to_save_queue': asyncio.Queue(),
        'error_queue': asyncio.Queue(),
        'watchdog_queue': asyncio.Queue(),
    }
    args = get_args()
    await read_history(args.history_file_path, queues)
    return await asyncio.gather(
        handle_connection(args.host, args.sending_port, args.token, args.reading_port, queues),
        save_messages(args.history_file_path, queues['messages_to_save_queue']),
        gui.draw(queues)
    )


# asyncio.run(main())
loop.run_until_complete(main())
