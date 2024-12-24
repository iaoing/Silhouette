import time

def timeit(func):
    """Decorator that prints the time a function takes to execute."""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        return result
    return wrapper

@timeit
def func():
    return True

t1 = time.perf_counter()
func()
t2 = time.perf_counter()
print(f"measured time: {t2-t1:.9f}")
