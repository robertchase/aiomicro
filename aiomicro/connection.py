"""http listener"""
import logging
import time

from aiohttp import HTTPReader, HTTPException, parse, format_server
from aiolistener import Connection

from aiomicro.database import DB
from aiomicro.rest import match


log = logging.getLogger(__package__)


class HTTPConnection(Connection):
    """concrete connection class for HTTP"""

    def __init__(self, routes, reader, writer):
        super().__init__(reader, writer)
        self.routes = routes

    def on_http_exception(self, exc):
        """write HTTP response"""
        self.writer.write(format_server(
            code=exc.code, message=exc.reason, content=exc.explanation))

    async def setup_reader(self):
        return HTTPReader(self.reader)

    async def next_packet(self):
        try:
            result = await parse(self.reader)
        except HTTPException as exc:
            if exc.explanation:
                log.warning("code=%s %s, cid=%s", exc.code, exc.explanation,
                            self.id)
            else:
                log.warning("code=%s, cid=%s", exc.code, self.id)
            self.on_http_exception(exc)
            result = None

        return result

    async def handle(self, packet, packet_id):
        r_start = time.perf_counter()

        message = (
            f"request cid={self.id}"
            f" rid={packet_id}, method={packet.http_method}"
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
            packet.cid = self.id
            packet.id = packet_id
            response = await handler(packet)

            if cursor:
                await cursor.commit()

            # --- send http response
            if response is None:
                response = ""
            self.writer.write(format_server(response))

        except HTTPException as exc:
            response_code = exc.code
            self.on_http_exception(exc)

        message += (
            f" status={response_code}"
            f" t={time.perf_counter() - r_start:f}")
        log.info(message)

        return packet.is_keep_alive
