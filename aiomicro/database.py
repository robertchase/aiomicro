"""setup database"""
import os

from aiodb import Cursor
# from aiodb.connector.postgres import DB as postgres_db

from aiomicro import micro
from aiomicro.micro.micro import _boolean


def setup(defn="micro"):
    """setup database from micro file"""
    database, _ = micro.parse(defn)
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

        async def _execute(query, **kwargs):
            """eat kwargs"""
            return await con.execute(query)

        return Cursor(
            execute=_execute,
            serialize=con.serialize,
            close=con.close,
            last_id=con.last_id,
            last_message=con.last_message,
            quote="`",
            transactions=commit,
        )

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

    async def cursor(self):
        """return connection to database as cursor"""
        return await self._connector()


DB = _DB()
