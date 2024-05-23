from os import listdir
from os import mkdir
from os.path import exists
from os.path import isdir
import argparse
import asyncio

from utils.core import logger
from utils.blum import Start
from utils.core import create_sessions

from database import on_startup_database
from database import actions as db_actions
from utils.telegram import Accounts

start_text = """
AnusSoft: https://t.me/cryptolamik

Select an action:

    1. Create session
    2. Run claimer
"""

# Функция для обработки действий


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--action', type=int, help='Action to perform')

    action = parser.parse_args().action

    if not action:
        print(start_text)

        while True:
            action = input("> ")

            if not action.isdigit():
                logger.warning("Action must be number")
            elif action not in ['1', '2']:
                logger.warning("Action must be 1 or 2")
            else:
                action = int(action)
                break

    await on_startup_database()

    if action == 1:
        await create_sessions()
    elif action == 2:
        accounts = await Accounts().get_accounts()
        tasks = []
        for account in accounts:
            session_proxy: str = await db_actions.get_session_proxy_by_name(session_name=account)

            tasks.append(asyncio.create_task(
                Start(session_name=account, session_proxy=session_proxy).main()))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    if not exists(path='sessions'):
        mkdir(path='sessions')

    session_files: list[str] = [current_file[:-8] if current_file.endswith('.session')
                                else current_file for current_file in listdir(path='sessions')
                                if current_file.endswith('.session') or isdir(s=f'sessions/{current_file}')]

    logger.info(f'Обнаружено {len(session_files)} сессий')

    asyncio.get_event_loop().run_until_complete(main())
