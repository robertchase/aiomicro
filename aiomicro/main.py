import asyncio
from functools import partial
import logging

from aiomicro.database import DB
from aiomicro.handler import on_connect
from aiomicro import micro


log = logging.getLogger(__name__)


class ConnectionCount:

    def __init__(self):
        self.count = 0

    def incr(self):
        self.count += 1
        return self.count


async def start_server(server):
    callback = partial(on_connect, server)
    log.info("starting server '%s' on port %d", server.name, server.port)
    listener = await asyncio.start_server(callback, port=server.port)
    log.info('listening on %s', listener.sockets[0].getsockname())
    return listener


async def main(defn='micro'):
    connection = ConnectionCount()
    database, servers = micro.parse(defn)
    if database:
        DB.setup(*database.args, **database.kwargs)
    for server in servers:
        server.connection = connection
        server.listener = await start_server(server)
    await asyncio.gather(
        *[server.listener.serve_forever() for server in servers]
    )


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())