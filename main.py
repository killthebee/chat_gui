import asyncio
import gui
import datetime
import aiofiles
import json

from errors import TokenError
from utils import (get_args, connect_to_chat, sanitize, save_token, is_token_file_exists, read_token_file,
                   delete_token_file)

loop = asyncio.get_event_loop()


async def read_history(filepath, messages_queue):
    async with aiofiles.open(filepath, 'r') as f:
        messages = await f.readlines()
        for message in messages:
            messages_queue.put_nowait(message)


async def read_msgs(host, port, messages_queue, messages_to_save_queue, status_update_queue):
    event = gui.ReadConnectionStateChanged.INITIATED
    status_update_queue.put_nowait(event)
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
        event = gui.ReadConnectionStateChanged.ESTABLISHED
        status_update_queue.put_nowait(event)
        while True:
            data = await reader.read(100)
            try:
                message = f"[{datetime.datetime.now().strftime('%d.%m.%y %H:%M')}] {data.decode()}"
                messages_queue.put_nowait(message)
                messages_to_save_queue.put_nowait(message)
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


async def run_message_sender(host, port, token, sending_queue, error_queue, status_update_queue):
    event = gui.SendingConnectionStateChanged.INITIATED
    status_update_queue.put_nowait(event)
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
        event = gui.SendingConnectionStateChanged.ESTABLISHED
        status_update_queue.put_nowait(event)
        authentication_result = await authenticate_token(reader, writer, token)
        if not authentication_result:
            error_queue.put_nowait(['Неверный токен', 'Проверьте токен, сервер его не узнал'])
            raise TokenError('Invalid token')
        else:
            event = gui.NicknameReceived(authentication_result['nickname'])
            status_update_queue.put_nowait(event)
        while True:
            message = await sending_queue.get()
            await send_message(writer, message)


async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_update_queue = asyncio.Queue()
    messages_to_save_queue = asyncio.Queue()
    error_queue = asyncio.Queue()

    args = get_args()
    await read_history(args.history_file_path, messages_queue)
    return await asyncio.gather(
        run_message_sender(args.host, args.sending_port, args.token, sending_queue, error_queue, status_update_queue),
        save_messages(args.history_file_path, messages_to_save_queue),
        read_msgs(args.host, args.reading_port, messages_queue, messages_to_save_queue, status_update_queue),
        gui.draw(messages_queue, sending_queue, status_update_queue, error_queue)
    )


# asyncio.run(main())
loop.run_until_complete(main())
