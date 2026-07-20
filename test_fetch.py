import os
import certifi
import traceback
from datetime import datetime, timedelta
from argopy import DataFetcher

import ssl
import aiohttp

# Disable SSL verification globally
ssl._create_default_https_context = ssl._create_unverified_context

# Monkey patch aiohttp to completely disable SSL checks
original_init = aiohttp.TCPConnector.__init__
def new_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    original_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = new_init

t2 = datetime.today()
t1 = t2 - timedelta(days=30)
print('Fetching...')
try:
    f = DataFetcher()
    ds = f.region([-70, -60, 30, 40, 0, 2000, t1.strftime('%Y-%m-%d'), t2.strftime('%Y-%m-%d')]).to_xarray()
    print('Success!')
    print(ds)
except Exception as e:
    print("FAILED")
    traceback.print_exc()
