import json

import tkinter as tk
from tkinter import messagebox

from utils import sanitize, connect_to_chat, save_token
from gui import update_tk


async def process_registration(host, port, path, logger, queues):
    while True:
        username = await queues['token_queue'].get()
        async with connect_to_chat(host, port) as connection:
            logger.info('Started auto registration')
            reader, writer = connection
            await reader.readline()
            writer.write('\n'.encode())
            await writer.drain()
            await reader.readline()
            writer.write(f'{sanitize(username)}\n'.encode())
            await writer.drain()
            response = await reader.readline()
            await save_token(json.loads(response)['account_hash'], path)
            logger.info('registered new user')
            root = await queues['register_tk_queue'].get()
            root.destroy()


def on_closing(root):
    if messagebox.askokcancel("Выйти", "Вы хотите завершить процесс регистрации?"):
        root.destroy()


def process_nickname(input_field, root, queues, logger):
    username = input_field.get()

    if len(username) > 0:
        logger.info('got the username')
        queues['register_tk_queue'].put_nowait(root)
        queues['token_queue'].put_nowait(sanitize(username))
        input_field.config(state='disabled')


async def register_new_user(logger, queues):
    root = tk.Tk()
    root.title('Регистрация')
    logger.info('initiate registration window')

    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))
    label = tk.Label(text='Введите желаемый \nникнейм')
    root_frame = tk.Frame()
    input_frame = tk.Frame(root_frame)
    input_field = tk.Entry(input_frame)
    button = tk.Button(
        root_frame,
        text='Зарегестрироваться',
        command=lambda: process_nickname(input_field, root, queues, logger),
    )

    label.grid(row=0, column=0)
    root_frame.grid(row=1, column=0)
    input_frame.grid(row=2, column=0)
    input_field.grid(row=2, column=1)
    button.grid(row=3, column=0)

    await update_tk(root_frame)
