import os

from aiodb.connector.mysql import DB as mysql_db
from aiodb.connector.postgres import DB as postgres_db

from aiomicro.micro.micro import _boolean


def setup_mysql(host='mysql', port=3306, name='', user='', password='',
                autocommit=None, isolation=None, debug=False, commit=True):
    host = os.getenv('DB_HOST', host)
    port = int(os.getenv('DB_PORT', port))
    name = os.getenv('DB_NAME', name)
    user = os.getenv('DB_USER', user)
    password = os.getenv('DB_PASSWORD', password)
    debug = _boolean(os.getenv('DB_DEBUG', debug))

    return mysql_db(
        host=host, port=port, user=user, password=password, database=name,
        autocommit=autocommit, isolation=isolation, debug=debug, commit=commit,
    )


def setup_postgres(host='mysql', port=3306, name='', user='', password='',
                   autocommit=None, debug=False, commit=True):
    host = os.getenv('DB_HOST', host)
    port = int(os.getenv('DB_PORT', port))
    name = os.getenv('DB_NAME', name)
    user = os.getenv('DB_USER', user)
    password = os.getenv('DB_PASSWORD', password)

    return postgres_db(
        host=host, port=port, user=user, password=password, database=name,
        autocommit=autocommit, debug=debug, commit=commit,
    )


class _DB:

    def __init__(self):
        self._db = None

    def setup(self, type, *args, **kwargs):

        if type == 'mysql':
            self._db = setup_mysql(*args, **kwargs)
        elif type == 'postgres':
            self._db = setup_postgres(*args, **kwargs)

    async def cursor(self):
        return await self._db.cursor()


DB = _DB()
