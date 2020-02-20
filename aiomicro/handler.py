import asyncio
from concurrent import futures
import logging
import time

from aiomicro.database import DB
from aiomicro.http import HTTPException, format_server
from aiomicro import rest


log = logging.getLogger(__name__)


async def read(reader):

    async def _read(reader):
        return await reader.read(5000)

    parser = rest.Parser()
    while parser.is_loading:
        data = await asyncio.wait_for(_read(reader), 5)
        if data:
            parser.handle(data)
    return parser.request


async def on_connect(server, reader, writer):
    cid = server.connection = server.connection + 1
    peerhost, peerport = writer.get_extra_info('peername')
    open = 'open server=%s socket=%s:%s, cid=%s' % (
        server.name, peerhost, peerport, cid)
    t_start = time.perf_counter()
    handler = None
    cursor = None

    try:
        request = await read(reader)
        open += ', method=%s, resource=%s' % (
            request.http_method, request.http_resource)
        handler = rest.match(server, request)
        if not handler.silent:
            log.info(open)
            open = None
        if handler.cursor:
            request.cursor = cursor = await DB.cursor()
            await request.cursor.start_transaction()
        request.cid = cid
        response = await handler(request)
        if cursor:
            await cursor.commit()
        if response is None:
            response = ''
        writer.write(format_server(content=response))
    except HTTPException as e:
        if open:
            log.info(open)
        if handler:
            handler.silent = False
        if e.explanation:
            log.warning('code=%s, (%s), cid=%s', e.code, e.explanation, cid)
        else:
            log.warning('code=%s, cid=%s', e.code, cid)
        writer.write(format_server(
            code=e.code, message=e.reason, content=e.explanation,
        ))
    # 3.8 except asyncio.exceptions.TimeoutError:
    except futures.TimeoutError:
        if open:
            log.info(open)
        if handler:
            handler.silent = False
        log.exception('timeout, cid=%s', cid)
        writer.write(format_server(
            code=400, message='Bad Request',
            content='timeout reading HTTP document',
        ))
    except Exception:
        if open:
            log.info(open)
        if handler:
            handler.silent = False
        log.exception('internal error, cid=%s', cid)
        writer.write(format_server(code=500, message='Internal Server Error'))
    finally:
        if cursor:
            await cursor.close()

    await writer.drain()
    t_elapsed = time.perf_counter() - t_start
    if not (handler and handler.silent):
        log.info('close cid=%s, t=%f', cid, t_elapsed)
    writer.close()
