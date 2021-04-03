"""start aiomicro server"""
import asyncio
import logging

from aioserver import Listeners

from aiomicro.database import DB
from aiomicro.listener import HTTPListener
from aiomicro.micro import parser


log = logging.getLogger(__name__)


async def main(defn="micro"):
    """parse micro definition file and start servers"""

    database, servers, tasks = parser.parse(defn)
    for connection_name, defn in database.items():
        con = DB.add(connection_name, *defn.args, **defn.kwargs)
        try:
            cursor = await con.cursor()
        except Exception as exc:
            raise Exception(
                f"unable to connect to database {connection_name}") from exc
        log.info("verified connectivity to database %s", connection_name)
        await cursor.close()
        if defn.pool:
            await con.init_pool(pool_size=defn.pool_size)
    for server in servers:
        listener = HTTPListener(server.name, server.port, server.routes)
        await Listeners.add(listener)
    for key, value in tasks.items():
        log.info("starting task %s", key)
        asyncio.create_task(value(), name=key)
    await Listeners.run()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
