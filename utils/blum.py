import random
from utils.core import logger
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestWebView
import asyncio
from urllib.parse import unquote
from data import config
import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from .headers import headers

# Заголовки HTTP-запросов
headers = {
    'Accept': '*/*',
    'Accept-Language': 'ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
    'Connection': 'keep-alive',
    'Origin': 'https://game-domain.blum',
    'Referer': 'https://game-domain.blum/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0',
    'sec-ch-ua': '"Microsoft Edge";v="123", "Not:A-Brand";v="8", "Chromium";v="123", "Microsoft Edge WebView2";v="123"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

# Класс для работы с клиентом Pyrogram


class Start:
    def __init__(self, thread: int, session_name: str, session_proxy: str | None = None):
        self.thread = thread
        self.session_name = session_name
        self.session_proxy = session_proxy
        if session_proxy:
            proxy = Proxy.from_str(session_proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None
        self.tg_client = Client(name=session_name,
                                workdir=config.WORKDIR,
                                proxy=proxy_dict
                                )
        self.session = aiohttp.ClientSession(headers=headers, trust_env=True)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as e:
            logger.error(f"Ошибка при проверке прокси: {e}")

    async def main(self):
        await self.tg_client.start()  # Начинаем сессию клиента перед использованием

        proxy_conn = ProxyConnector().from_url(self.session_proxy) if self.session_proxy else None

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn) as http_client:
            if self.session_proxy:
                await self.check_proxy(http_client=http_client, proxy=self.session_proxy)

            while True:
                try:
                    # Случайная задержка от 1 до 5 минут
                    await asyncio.sleep(random.uniform(60, 300))
                    await self.login(http_client=http_client, proxy=self.session_proxy)

                    while True:
                        try:
                            timestamp, start_time, end_time = await self.balance(http_client=http_client)

                            if start_time is None and end_time is None:
                                # Случайная задержка от 1 до 5 минут перед началом фарма
                                await asyncio.sleep(random.uniform(60, 300))
                                await self.start(http_client=http_client)
                                logger.info(f"Поток {self.thread} | Начало фарма!")

                            elif start_time is not None and end_time is not None and timestamp >= end_time:
                                timestamp, balance = await self.claim(http_client=http_client)
                                logger.success(
                                    f"Поток {self.thread} | Получена награда! Баланс: {balance}")
                                # Случайная задержка от 1 до 5 минут минут перед клеймом награды
                                await asyncio.sleep(random.uniform(60, 300))

                                timestamp, balance = await self.friend_claim(http_client=http_client)
                                logger.success(
                                    f"Поток {self.thread} | Получена награда за друзей! Баланс: {balance}")

                            else:
                                logger.info(
                                    f"Поток {self.thread} | Спим {end_time - timestamp} секунд!")
                                await asyncio.sleep(end_time - timestamp)

                            await asyncio.sleep(1)
                        except Exception as e:
                            logger.error(f"Поток {self.thread} | Ошибка: {e}")
                except Exception as e:
                    logger.error(f"Ошибка: {e}")

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        web_view = await self.tg_client.invoke(RequestWebView(
            peer=await self.tg_client.resolve_peer('BlumCryptoBot'),
            bot=await self.tg_client.resolve_peer('BlumCryptoBot'),
            platform='android',
            from_bot_menu=False,
            url='https://telegram.blum.codes/'
        ))

        auth_url = web_view.url
        return unquote(string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))

    async def claim(self, http_client: aiohttp.ClientSession):
        resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/claim")
        resp_json = await resp.json()

        return int(resp_json.get("timestamp")/1000), resp_json.get("availableBalance")

    async def friend_claim(self, http_client: aiohttp.ClientSession):
        resp = await http_client.post("https://gateway.blum.codes/v1/friends/claim")
        resp_json = await resp.json()

        timestamp = resp_json.get("timestamp")
        available_balance = resp_json.get("availableBalance")

        if timestamp is not None and available_balance is not None:
            return int(timestamp / 1000), available_balance
        else:
            logger.error(
                "Ошибка при клейме награды за друзей: неверный формат данных")
            return None, None

    async def start(self, http_client: aiohttp.ClientSession):
        resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/start")

    async def balance(self, http_client: aiohttp.ClientSession):
        resp = await http_client.get("https://game-domain.blum.codes/api/v1/user/balance")
        resp_json = await resp.json()

        timestamp = resp_json.get("timestamp")
        if resp_json.get("farming"):
            start_time = resp_json.get("farming").get("startTime")
            end_time = resp_json.get("farming").get("endTime")

            return int(timestamp/1000), int(start_time/1000), int(end_time/1000)
        return int(timestamp/1000), None, None

    async def login(self, http_client: aiohttp.ClientSession, proxy: str | None):
        json_data = {"query": await self.get_tg_web_data(proxy)}

        resp = await http_client.post("https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP", json=json_data)
        http_client.headers['Authorization'] = "Bearer " + (await resp.json()).get("token").get("access")
