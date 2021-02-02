"""setup database"""
import logging
import os

from aiodb import Cursor, Pool
# from aiodb.connector.postgres import DB as postgres_db

from aiomicro.micro import parser
from aiomicro.micro.action import _boolean


log = logging.getLogger(__name__)


def setup(defn="micro"):
    """setup database from micro file"""
    database, _, _ = parser.parse(defn)
    return _setup(*database.args, **database.kwargs)


def _setup(database_type, *args, **kwargs):
    """setup database connector by type"""

    if database_type == "mysql":
        return setup_mysql(*args, **kwargs)
    # if database_type == 'postgres':
    #     return setup_postgres(*args, **kwargs)

    return None


def setup_mysql(host="mysql",  # pylint: disable=too-many-arguments
                port=3306, name="", user="", password="", isolation=None,
                commit=True):
    """setup mysql connector"""
    from aiomysql.connection import MysqlConnection

    host = os.getenv("DB_HOST", host)
    port = int(os.getenv("DB_PORT", port))
    name = os.getenv("DB_NAME", name)
    user = os.getenv("DB_USER", user)
    password = os.getenv("DB_PASSWORD", password)
    isolation = os.getenv("DB_ISOLATION", isolation)
    commit = _boolean(os.getenv("DB_COMMIT", commit))

    async def cursor():
        con = await MysqlConnection.connect(
            host=host,
            user=user,
            password=password,
            database=name,
            port=port,
            autocommit=False,
            isolation=isolation,
        )

        async def no_kwargs(query, **kwargs):
            return await con.execute(query)

        return Cursor.bind(con, transactions=commit, execute=no_kwargs)

    return cursor


# def setup_postgres(host='mysql',  # pylint: disable=too-many-arguments
#                    port=3306, name='', user='', password='',
#                    autocommit=None, debug=False, commit=True):
#     """setup postgres connector"""
#     host = os.getenv('DB_HOST', host)
#     port = int(os.getenv('DB_PORT', port))
#     name = os.getenv('DB_NAME', name)
#     user = os.getenv('DB_USER', user)
#     password = os.getenv('DB_PASSWORD', password)
#
#     return postgres_db(
#         host=host, port=port, user=user, password=password, database=name,
#         autocommit=autocommit, debug=debug, commit=commit,
#     )


class _DB:

    def __init__(self):
        self._connector = None

    def setup(self, database_type, *args, **kwargs):
        """establish connector to database"""
        self._connector = _setup(database_type, *args, **kwargs)

    async def init_pool(self, pool_size):
        """set up connection pool"""
        pool = await Pool.setup(self.cursor, pool_size)
        self.cursor = pool.cursor

    async def cursor(self):
        """return connection to database as cursor"""
        return await self._connector()


DB = _DB()
