"""start aiomicro server"""
import asyncio
from functools import partial
import logging

from aiomicro.database import DB
from aiomicro.handler import on_connect
from aiomicro import micro


log = logging.getLogger(__name__)


async def start_server(server):
    """start a server on a port"""
    callback = partial(on_connect, server)
    log.info("starting server '%s' on port %d", server.name, server.port)
    listener = await asyncio.start_server(callback, port=server.port)
    log.info('listening on %s', listener.sockets[0].getsockname())
    return listener


async def main(defn='micro'):
    """parse micro definition file and start servers"""

    def sequence(current=1):
        """generate a sequence of integers"""
        while True:
            yield current
            current += 1

    connection_id = sequence()
    database, servers = micro.parse(defn)
    if database:
        DB.setup(*database.args, **database.kwargs)
    for server in servers:
        server.connection_id = connection_id
        server.listener = await start_server(server)
    await asyncio.gather(
        *[server.listener.serve_forever() for server in servers]
    )


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
