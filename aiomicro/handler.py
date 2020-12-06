"""handle an incoming http request"""
import asyncio
from collections import namedtuple
from concurrent import futures
import logging
import time

from aiomicro.database import DB
from aiomicro.http import HTTPException, format_server
from aiomicro import rest


log = logging.getLogger(__name__)


async def on_connect(server, reader, writer):
    """asyncio start_server callback"""
    reader = Reader(reader)
    cid = next(server.connection_id)
    peerhost, peerport = writer.get_extra_info('peername')
    open_msg = f"open server={server.name} socket={peerhost}:{peerport}"
    open_msg += f", cid={cid}"
    t_start = time.perf_counter()
    silent = False

    while True:
        result = await handle_request(server, reader, writer, cid)
        if not result.closed:
            silent = result.silent
        if not silent:
            if open_msg:
                log.info(open_msg)
            log.info(result.message)
        open_msg = None
        if not result.keep_alive:
            break

    await writer.drain()
    if not silent:
        t_elapsed = time.perf_counter() - t_start
        log.info("close cid=%s, t=%f", cid, t_elapsed)
    writer.close()


def _sequence(current=1):
    """generate a sequence of request ids"""
    while True:
        yield current
        current += 1


request_sequence = _sequence()


Result = namedtuple("Result", "message, keep_alive, silent, closed",
                    defaults=(False, False, False))


async def handle_request(server, reader, writer, cid):
    """handle a single request from the connection"""
    cursor = None
    message = f"request cid={cid}"
    try:
        r_start = time.perf_counter()

        # --- read next http document from socket
        request = await reader.read()
        if not request:
            return Result(f"remote close cid={cid}", closed=True)

        rid = next(request_sequence)
        message += f" rid={rid}, method={request.http_method}"
        message += f" resource={request.http_resource}"

        # --- identify handler based on method + resource
        handler = rest.match(server, request)

        if handler.cursor:
            request.cursor = cursor = await DB.cursor()
            await request.cursor.start_transaction()
        request.cid = cid
        request.id = rid

        # --- handle the request
        response = await handler(request)

        if cursor:
            await cursor.commit()

        # --- send http response
        if response is None:
            response = dict(content="")
        elif not isinstance(response, dict):
            response = dict(content=response)
        writer.write(format_server(**response))

        # --- return structured response
        message += f" t={time.perf_counter() - r_start:f}"
        return Result(message, request.is_keep_alive, handler.silent)
    except HTTPException as ex:
        if ex.explanation:
            log.warning("code=%s, (%s), cid=%s",
                        ex.code, ex.explanation, cid)
        else:
            log.warning("code=%s, cid=%s", ex.code, cid)
        writer.write(format_server(
            code=ex.code, message=ex.reason, content=ex.explanation,
        ))
        return Result(message)
    # 3.8 except asyncio.exceptions.TimeoutError:
    except futures.TimeoutError:
        log.exception("timeout, cid=%s", cid)
        writer.write(format_server(
            code=400, message="Bad Request",
            content="timeout reading HTTP document",
        ))
        return Result(message)
    except Exception:  # pylint: disable=broad-except
        log.exception("internal error, cid=%s", cid)
        writer.write(format_server(
            code=500, message="Internal Server Error"))
        return Result(message)
    finally:
        if cursor:
            await cursor.close()


class Reader:
    """read http messages from the specified stream"""

    def __init__(self, reader):
        self._reader = reader
        self._parser = rest.Parser()
        self._persistent = False

    async def read(self):
        """read and parse an http message"""

        async def _read():
            return await self._reader.read(5000)

        if self._persistent:
            self._parser.reset()  # clear previous request data

        while self._parser.is_loading:

            # for subsequent reads on persistent connections:
            if self._persistent:
                self._persistent = False
                self._parser.handle(b"")

            # all other reads:
            else:
                data = await asyncio.wait_for(_read(), 5)
                if not data:
                    return None
                self._parser.handle(data)

        self._persistent = True  # if we come back for more
        return self._parser.request
