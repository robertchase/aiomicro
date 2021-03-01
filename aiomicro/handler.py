"""handle an incoming http request"""
import asyncio
from collections import namedtuple
import logging
import time

from aiomicro.database import DB
import aiohttp
from aiomicro import rest


log = logging.getLogger(__name__)


def _sequence(current=1):
    """generate a sequence of request ids"""
    while True:
        yield current
        current += 1


connection_sequence = _sequence()
request_sequence = _sequence()


async def on_connect(server, reader, writer):
    """handler for inbound connection

       The server argument is an object with a name attribute used for logging,
       and routing information used by http_match.

       The reader and writer arguments are StreamReader and StreamWriter
       objects associated with an inbound client connection.
    """
    reader = http_reader(reader)
    cid = next(connection_sequence)

    peerhost, peerport = writer.get_extra_info("peername")
    open_msg = (
        f"open server={server.name} socket={peerhost}:{peerport}"
        f", cid={cid}")
    t_start = time.perf_counter()

    # sequentially handle each request on the stream
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


Result = namedtuple("Result", "message, keep_alive, silent, closed",
                    defaults=(False, False, False))


async def handle_request(server, reader, writer, cid, open_msg):
    """handle a single request from the connection"""
    cursor = None
    message = f"request cid={cid}"
    try:
        # --- read next http document from socket
        request = await http_parse(reader)
        r_start = time.perf_counter()

        rid = next(request_sequence)
        message += (
            f" rid={rid}, method={request.http_method}"
            f" resource={request.http_resource}")

        # --- identify handler based on method + resource
        handler = http_match(server, request)

        # --- display open message before handling request
        if open_msg:
            if not handler.silent:
                log.info(open_msg)

        # --- grab database connection
        if handler.cursor:
            cursor = await DB[handler.cursor]
            await cursor.start_transaction()
            request.cursor = cursor

        # --- handle the request
        request.cid = cid
        request.id = rid
        response = await handler(request)

        if cursor:
            await cursor.commit()

        # --- send http response
        if response is None:
            response = ""
        writer.write(http_format_server(response))

        # --- return structured response
        message += f" t={time.perf_counter() - r_start:f}"
        result = Result(message, request.is_keep_alive, handler.silent)
    except aiohttp.HTTPEOF as exc:
        if exc.is_timeout:
            msg = f"timeout close cid={cid}"
        else:
            msg = f"remote close cid={cid}"
        result = Result(msg, closed=True)
    except aiohttp.HTTPException as ex:
        if ex.explanation:
            log.warning("code=%s, %s, cid=%s",
                        ex.code, ex.explanation, cid)
        else:
            log.warning("code=%s, cid=%s", ex.code, cid)
        writer.write(on_http_exception(ex))
        result = Result(message)
    except asyncio.exceptions.TimeoutError:
        log.exception("timeout, cid=%s", cid)
        writer.write(on_timeout())
        result = Result(message)
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("internal error, cid=%s", cid)
        writer.write(on_exception(exc))
        result = Result(message)
    finally:
        if cursor:
            await cursor.close()

    return result


# --- patch these functions to modify behavior


def http_reader(reader):
    """wrap a StreamReader in an aiohttp.HTTPReader

       the primary reason for patching this call is to add parameters to the
       HTTPReader constructor in order to change default behavior
    """
    return aiohttp.HTTPReader(reader)


async def http_parse(reader):
    """parse an http document from reader"""
    return await aiohttp.parse(reader)


def http_match(server, request):
    """match http request against the routes in server

        returns an object with the following attributes:

            __call__ - accepts an http_document and returns data for an http
                       response
            silent   - flag that disables logging output
            cursor   - database name of a defined database connector found in
                       aiomicro.database.DB[name]. The connector is used to
                       obtain a database connection wrapped in an
                       aiodb.Cursor, which is added to the http_document as the
                       "cursor" attribute. If None, then no connection is made.
    """
    return rest.match(server, request)


def http_format_server(*args, **kwargs):
    """format data for http response

       see aiohttp.format_server for args + kwargs
    """
    return aiohttp.format_server(*args, **kwargs)


def on_http_exception(exc):
    """format http exception response back to client"""
    return http_format_server(
        code=exc.code, message=exc.reason, content=exc.explanation,
    )


def on_timeout():
    """format timeout response back to client"""
    return http_format_server(
        code=400, message="Bad Request",
        content="timeout reading HTTP document",
    )


def on_exception(exc):
    """format general exception response back to client"""
    return http_format_server(code=500, message="Internal Server Error")
