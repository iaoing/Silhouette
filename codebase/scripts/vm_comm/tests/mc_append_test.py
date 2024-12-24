import threading
from pymemcache.client.base import PooledClient
import datetime

# Connect to Memcached
client = PooledClient(('localhost', 11211))
client.flush_all()

# Initialize the key with an empty string if not already set
now = datetime.datetime.now()
ts = now.strftime('%Y%m%d%H%M%S%f')

key = f'append_test_{ts}'
client.set(key, '-1|')

def append_to_key(value):
    client.append(key, value)

# Function to be run by each thread
def thread_function(s, e):
    # print(f"thread: {s} - {e}")
    for i in range(s, e):
        value = f'{i}|'
        append_to_key(value)

def check_value():
    final_value = client.get(key).decode('utf-8')
    nums = final_value.split('|')
    # print(nums)
    print(len(nums))

# Create multiple threads
threads = []
for i in range(10):
    s = i * 10000
    e = (i+1)*10000
    thread = threading.Thread(target=thread_function, args=(s, e))
    threads.append(thread)
    thread.start()

# Wait for all threads to finish
for thread in threads:
    thread.join()


check_value()

