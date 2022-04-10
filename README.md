# Чат клиент с GUI

Подключает к чату, регистрирует если надо, даёт возможность читать и отправлять сообщения

<p align="center">
  <img src="https://github.com/killthebee/chat_gui/blob/master/pics/pic.png"/>
</p>

## Как установить

Для работы микросервиса нужен Python версии не ниже 3.6.

Установите зависимости

```bash
pip install -r requirements.txt
```

## Как запустить

```bash
python main.py 
```

## Первичные настройки

Вы можете указать следующие необязательные параметры работы программы при помощи флажков

```
python main.py --host minechat.dvmn.org
```
Адресс чата
```
python main.py --reading_port 5000
```
Порт для чтения
```
python main.py --sending_port 5000
```
Порт для отправки
```
python main.py --token_file_path chat.txt
```
Путь до файла в котором либо будет либо уже хранится токен для отправки сообщений
```
python main.py --history_file_path chat.txt
```
Путь до файла с историей сообщений чата
```
python main.py --token 61ea5d08-6aff-11ec-8c47-0242ac110002
```
Токен, с которым будет запущен скрипт отправки сообщений
# Цели проекта

Код написан в учебных целях — это урок в курсе по Python и веб-разработке на сайте [Devman](https://dvmn.org).