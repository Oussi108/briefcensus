"""Prints the software versions and CPU of the Kaggle session for the paper's settings table, then stops."""
import os
import platform

import lightgbm
import numpy
import pandas
import scipy

print('python', platform.python_version())
print('numpy', numpy.__version__)
print('scipy', scipy.__version__)
print('pandas', pandas.__version__)
print('lightgbm', lightgbm.__version__)
print('cores', os.cpu_count())
print('cpu', next((line.split(':')[1].strip() for line in open('/proc/cpuinfo') if line.startswith('model name')), 'unknown'))
print('memory', next((line.strip() for line in open('/proc/meminfo') if line.startswith('MemTotal')), 'unknown'))
