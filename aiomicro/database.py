"""setup database"""
import os

from aiodb.connector.mysql import DB as mysql_db
from aiodb.connector.postgres import DB as postgres_db

from aiomicro import micro
from aiomicro.micro.micro import _boolean


def setup(defn='micro'):
    """setup database from micro file"""
    database, _ = micro.parse(defn)
    return _setup(*database.args, **database.kwargs)


def _setup(database_type, *args, **kwargs):
    """setup database connector by type"""

    if database_type == 'mysql':
        return setup_mysql(*args, **kwargs)
    if database_type == 'postgres':
        return setup_postgres(*args, **kwargs)

    return None


def setup_mysql(host='mysql',  # pylint: disable=too-many-arguments
                port=3306, name='', user='', password='',
                autocommit=None, isolation=None, debug=False, commit=True):
    """setup mysql connector"""
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


def setup_postgres(host='mysql',  # pylint: disable=too-many-arguments
                   port=3306, name='', user='', password='',
                   autocommit=None, debug=False, commit=True):
    """setup postgres connector"""
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

    def setup(self, database_type, *args, **kwargs):
        """establish connector to database"""
        self._db = _setup(database_type, *args, **kwargs)

    async def cursor(self):
        """return connection to database as cursor"""
        return await self._db.cursor()


DB = _DB()
