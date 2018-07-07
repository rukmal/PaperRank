from .database_abstract import DatabaseAbstractClass
from functools import wraps
import logging
from redis.client import StrictRedis
import redis

# CONSTANTS
# ==========

# Abbreviation-key mapping
ABBR = {
    'O': 'OUT',
    'S': 'SEEN',
    'G': 'GRAPH',
    'E': 'EXPLORE',
    'I': 'INSTANCE',
    'N': 'NOT',
    'L': 'LOG',
    'D': 'DANGLING'
}


class _Decorators:
    @classmethod
    def verifyDatabase(cls, decorated):
        """Decorator to verify that the database being requested is valid,
        if so update with the full database name.
        """

        @wraps(decorated)
        def wrapper(*args, **kwargs):
            if kwargs['database'] not in ABBR.keys():
                raise RuntimeError('Unknown database name provided.')
            kwargs['database'] = ABBR[kwargs['database']]
            return decorated(*args, **kwargs)
        return wrapper


class Redis(DatabaseAbstractClass):

    def __init__(self, host: str, port: int, db: int):
        """Connect to the Redis database.
        
        Arguments:
            host {str} -- Hostname of the database.
            port {int} -- Port number of the database.
            db {int} -- Database number to connect to.
        
        Raises:
            RuntimeError -- Raised if the database connection failed.
        """

        # Mapping types
        self.db = {
            'OUT': self.__RedisHashMap,
            'SEEN': self.__RedisSet,
            'GRAPH': self.__RedisSet,
            'EXPLORE': self.__RedisSet,
            'INSTANCE': self.__RedisSet,
            'NOT': self.__RedisSet,
            'DANGLING': self.__RedisSet,
            'LOG': self.__RedisSet
        }

        # Connect to Redis
        pool = redis.ConnectionPool(host=host, port=port, db=db)
        self.r = redis.StrictRedis(connection_pool=pool)
        self.checkConnection()

    def checkConnection(self) -> bool:
        """Check the Redis database connection.
        
        Raises:
            RuntimeError -- Raised if the database connection failed.
        
        Returns:
            bool -- True if connection is successful.
        """

        # Attempt ping
        try:
            return self.r.ping()
        except redis.exceptions.ConnectionError:
            logging.error('Redis database connection failed.')
            raise RuntimeError('Redis connection failed.')

    @_Decorators.verifyDatabase
    def contains(self, database: str, key: str) -> bool:
        """Check if a given key exists in the Redis database.
        
        Arguments:
            database {str} -- Name of the database.
            key {str} -- Key to be checked.
        
        Returns:
            bool -- True if it exists, false otherwise.
        """

        return self.db[database].contains(r=self.r, database=database, key=key)

    @_Decorators.verifyDatabase
    def addMultiple(self, database: str, data: object) -> bool:
        """Add multiple values/data to the given database.
        
        Arguments:
            database {str} -- Database data should be added to.
            data {object} -- List if adding to Set, Dict if adding to HashMap.
        
        Returns:
            bool -- True if successful, False otherwise.
        """

        return self.db[database].addMultiple(
            r=self.r, database=database, values=data)

    @_Decorators.verifyDatabase
    def removeMultiple(self, database: str, data: list) -> bool:
        """Remove multiple values from the given database.
        
        Arguments:
            database {str} -- Database data should be removed from.
            data {list} -- List of keys/data to be removed.
        
        Returns:
            bool -- True if successful, False otherwise.
        """

        out = self.db[database].removeMultiple(
            r=self.r, database=database, data=data)
        return out is not None

    @_Decorators.verifyDatabase
    def pop(self, database: str, n: int=1) -> list:
        """Removes and returns `n` elements from a Set.
        
        Arguments:
            database {str} -- Database elements are popped from.
        
        Keyword Arguments:
            n {int} -- Number of elements to return (default: {1}).
        
        Returns:
            list -- Popped elements.
        """

        return self.db[database].pop(r=self.r, database=database, n=n)

    @_Decorators.verifyDatabase
    def size(self, database: str) -> int:
        """Return the size of a given database. Number of keys returned
        for HashMap, and the number of elements for a Set.
        
        Arguments:
            r {object} -- [description]
            database {str} -- Database for which size is returned.
        
        Returns:
            int -- Size of the database.
        """

        return self.db[database].size(r=self.r, database=database)

    @_Decorators.verifyDatabase
    def isEmpty(self, database: str) -> bool:
        """Function to check if a given database is empty.
        
        Arguments:
            database {str} -- Database to be checked.
        
        Returns:
            bool -- True if empty, False if not empty.
        """

        # NOTE: Redis automatically deletes empty Sets and Hashes,
        #       so this replicates the desired functionality in O(1).
        return not self.r.exists(database)

    class __RedisSet:
        """Subclass for Redis Set datastructure operations.
        """

        @staticmethod
        def contains(r: object, database: str, key: str) -> bool:
            return r.sismember(name=database, value=key)

        @staticmethod
        def addMultiple(r: object, database: str, values: list) -> bool:
            return r.sadd(database, *values)

        @staticmethod
        def removeMultiple(r: object, database: str, data: list) -> int:
            return r.srem(database, *data)

        @staticmethod
        def pop(r: object, database: str, n: int) -> list:
            # Note: Doing it this way because `redis` has a bug
            # where the spop(count) function does not work.
            popped = r.srandmember(name=database, number=n)
            # Removing popped elements
            r.srem(database, *popped)
            return popped

        @staticmethod
        def size(r: object, database: str) -> int:
            return r.scard(database)

    class __RedisHashMap:
        """Subclass for Redis HashMap data structure operations.
        """

        @staticmethod
        def contains(r: StrictRedis, database: str, key: str) -> bool:
            return r.hexists(name=database, key=key)

        @staticmethod
        def addMultiple(r: object, database: str, values: dict) -> bool:
            return r.hmset(database, values)

        @staticmethod
        def removeMultiple(r: object, database: str, data: list) -> int:
            return r.hdel(database, *data)

        @staticmethod
        def pop(r: object, database: str, n: int) -> bool:
            raise NotImplementedError

        @staticmethod
        def size(r: object, database: str) -> int:
            return r.hlen(database)
