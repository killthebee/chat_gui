import os
import argparse
import asyncio
import aiofiles

from socket import gaierror
from contextlib import asynccontextmanager
from pathlib import Path


def get_args():
    """
    default value is suitable only for message sender, thus won't work in message reader
    file_path: might be either file with token for message sender or file with chat logs for reader
    :return: arguments
    """
    parser = argparse.ArgumentParser(description='program settings')
    parser.add_argument('--host', default='minechat.dvmn.org', help='chat ip')
    parser.add_argument('--reading_port', default='5000', help='chat port')
    parser.add_argument('--sending_port', default='5050', help='chat port')
    parser.add_argument('--history_file_path', default='chat.txt', help='path to history txt file')
    parser.add_argument('--token_file_path', default='token.txt', help='path to token txt file')
    parser.add_argument('--token', default='7c12802a-7770-11ec-8c47-0242ac110002', help='token for authorization in message sending server')
    args = parser.parse_args()
    return args


async def save_token(token, path):
    async with aiofiles.open(path, 'w') as f:
        await f.write(token)


def is_token_file_exists(path):
    token_file = Path(path)
    return token_file.is_file()


async def read_token_file(path):
    if not is_token_file_exists(path):
        return None
    async with aiofiles.open(path) as token_file:
        return await token_file.read()


def delete_token_file(path):
    if not is_token_file_exists(path):
        return None
    os.remove(path)


@asynccontextmanager
async def connect_to_chat(host, port):
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
        except gaierror:  # gaiiii
            await asyncio.sleep(1)
            continue
        try:
            yield reader, writer
        finally:
            writer.close()


def sanitize(message):
    return message.replace('\n', '').replace('\r', '')

