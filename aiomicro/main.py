"""start aiomicro server"""
import asyncio
from functools import partial
import logging

from aiomicro.database import DB
from aiomicro.handler import on_connect
from aiomicro.micro import parser


log = logging.getLogger(__name__)


async def start_server(server):
    """start a server on a port"""
    callback = partial(on_connect, server)
    log.info("starting server '%s' on port %d", server.name, server.port)
    listener = await asyncio.start_server(callback, port=server.port)
    log.info('listening on %s', listener.sockets[0].getsockname())
    return listener


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
        server.listener = await start_server(server)
    for key, value in tasks.items():
        log.info("starting task %s", key)
        asyncio.create_task(value(), name=key)
    await asyncio.gather(
        *[server.listener.serve_forever() for server in servers])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
