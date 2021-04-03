"""http listener"""
import logging
import time

from aiohttp import HTTPReader, HTTPException, parse, format_server
from aioserver import Listener

from aiomicro.database import DB
from aiomicro.rest import match


log = logging.getLogger(__package__)


def on_http_exception(exc, writer, cid, pid=None):
    writer.write(format_server(
        code=exc.code, message=exc.reason, content=exc.explanation))


class HTTPListener(Listener):

    def __init__(self, name, port, routes):
        super().__init__(name, port)
        self.routes = routes

    @staticmethod
    async def set_reader(reader):
        return HTTPReader(reader)

    @staticmethod
    async def next_packet(reader, writer, cid):
        try:
            result = await parse(reader)
        except HTTPException as exc:
            if exc.explanation:
                log.warning("code=%s %s, cid=%s", exc.code, exc.explanation,
                            cid)
            else:
                log.warning("code=%s, cid=%s", exc.code, cid)
            on_http_exception(exc, writer, cid)
            result = None

        return result

    async def handle(self, packet, writer, cid, pid):
        r_start = time.perf_counter()

        message = (
            f"request cid={cid}"
            f" rid={pid}, method={packet.http_method}"
            f" resource={packet.http_resource}")
        response_code = 200

        # --- identify handler based on method + resource
        try:
            handler = match(self.routes, packet)

            # --- grab database connection
            if handler.cursor:
                cursor = await DB[handler.cursor]
                await cursor.start_transaction()
                packet.cursor = cursor
            else:
                cursor = None

            # --- handle the request
            packet.cid = cid
            packet.id = pid
            response = await handler(packet)

            if cursor:
                await cursor.commit()

            # --- send http response
            if response is None:
                response = ""
            writer.write(format_server(response))

        except HTTPException as exc:
            response_code = exc.code
            on_http_exception(exc, writer, cid, pid)

        message += (
            f" status={response_code}"
            f" t={time.perf_counter() - r_start:f}")
        log.info(message)

        return packet.is_keep_alive
