"""start aiomicro server"""
import asyncio
from functools import partial
import logging

from aioserver import Listeners

from aiomicro.database import DB
from aiomicro.connection import HTTPConnection
from aiomicro.micro import parser


log = logging.getLogger(__name__)


async def main(defn="micro"):
    """parse micro definition file and start servers"""

    database, servers, tasks = parser.parse(defn)
    for connection_name, setup in database.items():
        con = DB.add(connection_name, *setup.args, **setup.kwargs)
        try:
            cursor = await con.cursor()
        except Exception as exc:
            raise Exception(
                f"unable to connect to database {connection_name}") from exc
        log.info("verified connectivity to database %s", connection_name)
        await cursor.close()
        if setup.pool:
            await con.init_pool(pool_size=setup.pool_size)
    for server in servers:
        connection = partial(HTTPConnection, server.routes)
        await Listeners.add(server.name, server.port, connection)
    for key, value in tasks.items():
        log.info("starting task %s", key)
        asyncio.create_task(value(), name=key)
    await Listeners.run()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
