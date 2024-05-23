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
from fake_useragent import UserAgent

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
    'User-Agent': UserAgent(os='android').random,
    'sec-ch-ua': '"Microsoft Edge";v="123", "Not:A-Brand";v="8", "Chromium";v="123", "Microsoft Edge WebView2";v="123"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}


class Start:
    def __init__(self, session_name: str, session_proxy: str | None = None):
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
            logger.error(f"Ошибка при проверке прокси акк{self.session_name}: {e}")


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
                            msg = await self.claim_daily_reward(http_client=http_client)
                            if isinstance(msg, bool) and msg:
                                logger.success(f"Поток {self.session_name} | Ежедневные награды получены!")

                            timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)

                            while play_passes:
                                game_id = await self.start_game(http_client=http_client)
                                if not game_id:
                                    logger.error(f"Поток {self.session_name} | Ошибка с началом игры!")
                                    continue

                                logger.info(f"Поток {self.session_name} | Начал играть в игру! GameId: {game_id}")

                                msg, points = await self.claim_game(game_id, http_client=http_client)
                                if isinstance(msg, bool) and msg:
                                    logger.success(f"Поток {self.session_name} | Закончил игру с результатом: {points}")
                                else:
                                    logger.error(f"Поток {self.session_name} | Ошибка при клейме игры: {msg}")

                                await asyncio.sleep(random.uniform(5, 10))
                                timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)

                            if start_time is None and end_time is None:
                                # Случайная задержка от 1 до 5 минут перед началом фарма
                                await asyncio.sleep(random.uniform(60, 300))
                                await self.start(http_client=http_client)
                                logger.info(f"Поток {self.session_name} | Начало фарма!")

                            elif start_time is not None and end_time is not None and timestamp >= end_time:
                                timestamp, balance = await self.claim(http_client=http_client)
                                logger.success(
                                    f"Поток {self.session_name} | Получена награда! Баланс: {balance}")
                                # Случайная задержка от 1 до 5 минут минут перед клеймом награды
                                await asyncio.sleep(random.uniform(60, 300))

                                timestamp, balance = await self.friend_claim(http_client=http_client)
                                logger.success(
                                    f"Поток {self.session_name} | Получена награда за друзей! Баланс: {balance}")

                            else:
                                logger.info(
                                    f"Поток {self.session_name} | Спим {end_time - timestamp} секунд!")
                                await asyncio.sleep(end_time - timestamp)

                            await asyncio.sleep(1)
                        except Exception as e:
                            logger.error(f"Поток {self.session_name} | Ошибка: {e}")
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

            return int(timestamp/1000), int(start_time/1000), int(end_time/1000), resp_json.get("playPasses")
        return int(timestamp/1000), None, None, resp_json.get("playPasses")
    

    async def claim_daily_reward(self, http_client: aiohttp.ClientSession):
        resp = await http_client.post("https://game-domain.blum.codes/api/v1/daily-reward?offset=-180")
        txt = await resp.text()
        await asyncio.sleep(random.uniform(60, 200))

        return True if txt == 'OK' else txt
    

    async def start_game(self, http_client: aiohttp.ClientSession):
        await asyncio.sleep(random.uniform(30, 100))
        resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/play")
        resp_json = await resp.json()

        return (resp_json).get("gameId")
    

    async def claim_game(self, game_id: str, http_client: aiohttp.ClientSession):
        await asyncio.sleep(random.uniform(50, 80))
        points = random.randint(70, 150)
        json_data = {"gameId": game_id, "points": points}
        resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data)
        txt = await resp.text()

        return True if txt == 'OK' else txt, points


    async def login(self, http_client: aiohttp.ClientSession, proxy: str | None):
        json_data = {"query": await self.get_tg_web_data(proxy)}

        resp = await http_client.post("https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP", json=json_data)
        http_client.headers['Authorization'] = "Bearer " + (await resp.json()).get("token").get("access")
