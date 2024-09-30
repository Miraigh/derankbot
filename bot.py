import discord
from discord.ext import tasks
import asyncio
import json
from siegeapi import Auth
import pyotp
from flask import Flask, render_template
import threading
import os
import sys

# Опционально: Загрузка переменных окружения из .env файла для локальной разработки
# from dotenv import load_dotenv
# load_dotenv()

# Загрузка конфигурации из config.json с явным указанием кодировки
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    print("Файл config.json не найден.")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"Ошибка синтаксиса в config.json: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Неизвестная ошибка при загрузке config.json: {e}")
    sys.exit(1)

# Загрузка токена из переменных окружения
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = config.get('channel_id')
MESSAGE_ID = config.get('message_id')
ACCOUNTS = config.get('accounts', [])

if not DISCORD_TOKEN:
    print("Переменная окружения DISCORD_TOKEN не установлена.")
    sys.exit(1)

if not CHANNEL_ID or not MESSAGE_ID:
    print("Отсутствуют необходимые параметры в config.json.")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

app = Flask(__name__)

# Маршрут для главной страницы Flask
@app.route('/')
def home():
    return render_template('index.html')

async def fetch_account_info(account):
    auth = Auth(account['ubisoft_email'], account['ubisoft_password'])
    try:
        player = await auth.get_player(name=account['nickname'])
        await player.load_ranked_v2()

        rank = player.ranked_profile.rank
        # Генерация 2FA кода
        totp = pyotp.TOTP(account['secret_key'])
        two_fa_code = totp.now()

        await auth.close()

        return {
            "nickname": player.name,
            "rank": rank,
            "login": account['ubisoft_email'],
            "password": account['ubisoft_password'],
            "2fa_code": two_fa_code
        }
    except Exception as e:
        print(f"Ошибка для аккаунта {account['nickname']}: {e}")
        return {
            "nickname": account.get('nickname', 'Неизвестный'),
            "rank": "Ошибка",
            "login": account.get('ubisoft_email', 'Неизвестный'),
            "password": account.get('ubisoft_password', 'Неизвестный'),
            "2fa_code": "Ошибка"
        }

async def get_all_accounts_info():
    tasks = [fetch_account_info(account) for account in ACCOUNTS]
    return await asyncio.gather(*tasks)

@client.event
async def on_ready():
    print(f'Вошёл как {client.user}')
    update_message.start()

@tasks.loop(seconds=30)
async def update_message():
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print("Канал не найден.")
        return
    try:
        message = await channel.fetch_message(MESSAGE_ID)
    except discord.NotFound:
        print("Сообщение не найдено.")
        return
    except discord.Forbidden:
        print("Нет доступа к сообщению.")
        return
    except discord.HTTPException as e:
        print(f"HTTP ошибка при получении сообщения: {e}")
        return

    accounts_info = await get_all_accounts_info()

    embed = discord.Embed(title="Мои аккаунты Rainbow Six", color=0x00ff00)
    for info in accounts_info:
        embed.add_field(
            name=info['nickname'],
            value=f"**Ранг:** {info['rank']}\n**Логин:** {info['login']}\n**Пароль:** {info['password']}\n**2FA Код:** {info['2fa_code']}",
            inline=False
        )

    try:
        await message.edit(embed=embed)
        print("Сообщение успешно обновлено.")
    except discord.HTTPException as e:
        print(f"Ошибка при обновлении сообщения: {e}")

def run_flask():
    # Получение порта из переменной окружения или использование 5000 по умолчанию
    port = int(os.environ.get("PORT", 5000))
    print(f"Запуск Flask-сервера на порту {port}...")
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запуск Flask-сервера в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    # Запуск Discord-бота
    client.run(DISCORD_TOKEN)
