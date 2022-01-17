import asyncio
import gui
import datetime
import aiofiles
import json

from utils import (get_args, connect_to_chat, sanitize, save_token, is_token_file_exists, read_token_file,
                   delete_token_file)

loop = asyncio.get_event_loop()


async def read_history(filepath, messages_queue):
    async with aiofiles.open(filepath, 'r') as f:
        messages = await f.readlines()
        for message in messages:
            messages_queue.put_nowait(message)


async def read_msgs(host, port, messages_queue, messages_to_save_queue):
    async with connect_to_chat(host, port) as connection:
        reader, writer = connection
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


async def send_message(queue):
    while True:
        message = await queue.get()
        print(message)


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


async def is_authentic_token(reader, writer, token):
    writer.write(f'{sanitize(token)}\n\n'.encode())
    await writer.drain()
    for _ in range(0, 2):
        results = await reader.readline()
        print(f'HHMMM {results.decode()}')
    return not json.loads(results) is None


async def run_message_sender(host, port, path):
    while True:
        if not is_token_file_exists(path):
            await asyncio.sleep(0)
            continue

        async with connect_to_chat(host, port) as connection:
            reader, writer = connection
            token = await read_token_file(path)

            if not await is_authentic_token(reader, writer, token):
                delete_token_file(path)
                continue

            while True:
                print('LOGGINED IN!!!')
                await asyncio.sleep(10)
            #     message = input('write message: ')
            #     await send_message(writer, message)


async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_update_queue = asyncio.Queue()
    messages_to_save_queue = asyncio.Queue()

    args = get_args()
    await read_history(args.history_file_path, messages_queue)
    return await asyncio.gather(
        run_token_handler(args.host, args.sending_port, args.token_file_path, args.token),
        run_message_sender(args.host, args.sending_port, args.token_file_path),
        send_message(sending_queue),
        save_messages(args.history_file_path, messages_to_save_queue),
        read_msgs(args.host, args.reading_port, messages_queue, messages_to_save_queue),
        gui.draw(messages_queue, sending_queue, status_update_queue)
    )


# asyncio.run(main())
loop.run_until_complete(main())
