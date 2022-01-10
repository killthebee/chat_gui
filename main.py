import asyncio
import gui
import datetime
import aiofiles

from utils import get_args, connect_to_chat


loop = asyncio.get_event_loop()

messages_queue = asyncio.Queue()
sending_queue = asyncio.Queue()
status_update_queue = asyncio.Queue()
messages_to_save_queue = asyncio.Queue()


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


async def main():
    args = get_args()
    await read_history(args.file_path, messages_queue)
    return await asyncio.gather(
        save_messages(args.file_path, messages_to_save_queue),
        read_msgs(args.host, args.port, messages_queue, messages_to_save_queue),
        gui.draw(messages_queue, sending_queue, status_update_queue)
    )

# asyncio.run(main())
loop.run_until_complete(main())
