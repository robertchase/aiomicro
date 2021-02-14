"""handle an incoming http request"""
import asyncio
from collections import namedtuple
import logging
import time

from aiomicro.database import DB
import aiohttp
from aiomicro import rest


log = logging.getLogger(__name__)


async def on_connect(server, reader, writer):
    """asyncio start_server callback"""
    reader = aiohttp.HTTPReader(reader)
    cid = next(server.connection_id)

    peerhost, peerport = writer.get_extra_info("peername")
    open_msg = (
        f"open server={server.name} socket={peerhost}:{peerport}"
        f", cid={cid}")
    t_start = time.perf_counter()

    silent = False
    keep_alive = True
    while keep_alive:
        result = await handle_request(server, reader, writer, cid, open_msg)
        if not result.closed:
            silent = result.silent
        if not silent:
            log.info(result.message)
        open_msg = None
        keep_alive = result.keep_alive

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


async def handle_request(server, reader, writer, cid, open_msg):
    """handle a single request from the connection"""
    cursor = None
    message = f"request cid={cid}"
    try:
        r_start = time.perf_counter()

        # --- read next http document from socket
        request = await aiohttp.parse(reader)

        rid = next(request_sequence)
        message += (
            f" rid={rid}, method={request.http_method}"
            f" resource={request.http_resource}")

        # --- identify handler based on method + resource
        handler = rest.match(server, request)

        # --- display open message before handling request
        if open_msg:
            if not handler.silent:
                log.info(open_msg)

        # --- grab database connection
        if handler.cursor:
            cursor = await DB.cursor()
            await cursor.start_transaction()

        # --- handle the request
        request.cursor = cursor
        request.cid = cid
        request.id = rid
        response = await handler(request)

        if cursor:
            await cursor.commit()

        # --- send http response
        if response is None:
            response = ""
        writer.write(aiohttp.format_server(response))

        # --- return structured response
        message += f" t={time.perf_counter() - r_start:f}"
        return Result(message, request.is_keep_alive, handler.silent)
    except aiohttp.HTTPEOF:
        return Result(f"remote close cid={cid}", closed=True)
    except aiohttp.HTTPException as ex:
        if ex.explanation:
            log.warning("code=%s, (%s), cid=%s",
                        ex.code, ex.explanation, cid)
        else:
            log.warning("code=%s, cid=%s", ex.code, cid)
        writer.write(aiohttp.format_server(
            code=ex.code, message=ex.reason, content=ex.explanation,
        ))
        return Result(message)
    except asyncio.exceptions.TimeoutError:
        log.exception("timeout, cid=%s", cid)
        writer.write(aiohttp.format_server(
            code=400, message="Bad Request",
            content="timeout reading HTTP document",
        ))
        return Result(message)
    except Exception:  # pylint: disable=broad-except
        log.exception("internal error, cid=%s", cid)
        writer.write(aiohttp.format_server(
            code=500, message="Internal Server Error"))
        return Result(message)
    finally:
        if cursor:
            await cursor.close()
