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

from utils import get_args, connect_to_chat, sanitize, read_token_file
from register_new_user import register_new_user, process_registration

loop = asyncio.get_event_loop()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('watchdog_logger')


async def read_history(filepath, queues):
    async with aiofiles.open(filepath, 'r') as f:
        messages = await f.readlines()
        for message in messages:
            queues['messages_queue'].put_nowait(message)


async def read_msgs(queues, reader):
    data = await reader.read(100)
    queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection is alive. Source: New message in chat')
    message = f"[{datetime.datetime.now().strftime('%d.%m.%y %H:%M')}] {data.decode()}"
    queues['messages_queue'].put_nowait(message)
    queues['messages_to_save_queue'].put_nowait(message)


async def read_msgs_handler(host, port, queues):
    event = gui.ReadConnectionStateChanged.INITIATED
    queues['status_update_queue'].put_nowait(event)
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
        event = gui.ReadConnectionStateChanged.ESTABLISHED
        queues['status_update_queue'].put_nowait(event)
        while True:
            try:
                await read_msgs(queues, reader)
            except UnicodeDecodeError:
                continue


async def save_messages(filepath, queue):
    while True:
        message = await queue.get()
        async with aiofiles.open(filepath, 'a') as f:
            await f.write(message)


async def send_message(writer, queues):
    while True:
        message = await queues['sending_queue'].get()
        writer.write(f'{sanitize(message)}\n\n'.encode())
        await writer.drain()


async def authenticate_token(reader, writer, token):
    writer.write(f'{sanitize(token)}\n\n'.encode())
    await writer.drain()
    for _ in range(0, 2):
        results = await reader.readline()
    return json.loads(results)


async def ping_pong(reader, writer, queues):
    while True:
        writer.write('\n'.encode())
        await writer.drain()
        await reader.readline()
        queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection to send server is alive. Ping message sent')
        await asyncio.sleep(3)


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
            async with create_task_group() as sending_group:
                sending_group.start_soon(ping_pong, reader, writer, queues)
                sending_group.start_soon(send_message, writer, queues)
                queues['watchdog_queue'].put_nowait(f'[{time.time()}] Connection is alive. Message sent')


async def watch_for_read_connection(queues):
    timeout_sum = 0
    while True:
        try:
            async with timeout(3):
                event = await queues['watchdog_queue'].get()
                timeout_sum = 0
                logger.info(event)

        except TimeoutError:
            if timeout_sum >= 3:
                event = gui.ReadConnectionStateChanged.CLOSED
                queues['status_update_queue'].put_nowait(event)
                raise ConnectionError
            timeout_sum += 1
            logger.info(f"{timeout_sum}s timeout is elapsed")


async def handle_connection(host, sending_port, token, reading_port, queues):
    while True:
        try:
            async with create_task_group() as tg:
                tg.start_soon(run_message_sender, host, sending_port, token, queues)
                tg.start_soon(read_msgs_handler, host, reading_port, queues)
                tg.start_soon(watch_for_read_connection, queues)
        except ConnectionError:
            logger.info('Reconnecting to server')
            await asyncio.sleep(1)


async def token_handler(token, token_file_path, host, sending_port, queues):
    if not token:
        token = await read_token_file(token_file_path)
    if not token:
        try:
            async with create_task_group() as register_task_group:
                register_task_group.start_soon(register_new_user, logger, queues)
                register_task_group.start_soon(
                    process_registration, host, sending_port, token_file_path, logger, queues
                )
        except gui.TkAppClosed:
            token = await read_token_file(token_file_path)
            if token:
                await asyncio.sleep(1)
            else:
                raise gui.TkAppClosed
    return token


async def main():
    queues = {
        'messages_queue': asyncio.Queue(),
        'sending_queue': asyncio.Queue(),
        'status_update_queue': asyncio.Queue(),
        'messages_to_save_queue': asyncio.Queue(),
        'error_queue': asyncio.Queue(),
        'watchdog_queue': asyncio.Queue(),
        'token_queue': asyncio.Queue(),
        'register_tk_queue': asyncio.Queue(),
    }
    args = get_args()
    token = await token_handler(
        args.token, args.token_file_path, args.host, args.sending_port, queues
    )

    await read_history(args.history_file_path, queues)
    async with create_task_group() as tg:
        tg.start_soon(handle_connection, args.host, args.sending_port, token, args.reading_port, queues)
        tg.start_soon(save_messages, args.history_file_path, queues['messages_to_save_queue'])
        tg.start_soon(gui.draw, queues)


loop.run_until_complete(main())
