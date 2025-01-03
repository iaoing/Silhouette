class CachelineBase:
    pass

class CacheBase:
    # accept an operation
    def accept(op):
        raise NotImplementedError

    # flush all the stores marked with flushed
    def flush():
        raise NotImplementedError

    # get all the stores in the cache
    def get_stores():
        raise NotImplementedError

    # get all the stores marked with flushed in the cache
    def get_stores_to_flush():
        raise NotImplementedError

    # get all the cachelines in the cache
    def get_cachelines():
        raise NotImplementedError

    # get all the cachelines marked with flushed in the cache
    def get_cachelines_to_flush():
        raise NotImplementedError