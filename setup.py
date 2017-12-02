#!/usr/bin/env python
from setuptools import setup

try:
    from Cython.Build import cythonize
    import numpy as np
    ext_modules = cythonize([
        'astrid/io.pyx', 
        'astrid/server.pyx', 
        'astrid/orc.pyx', 
        'astrid/workers.pyx', 
        'astrid/names.pyx', 
        'astrid/mixer.pyx', 
    ], include_path=[np.get_include()]) 

except ImportError:
    from setuptools.extension import Extension
    ext_modules = [
        Extension('astrid.io', ['astrid/io.c']), 
        Extension('astrid.server', ['astrid/server.c']), 
        Extension('astrid.orc', ['astrid/orc.c']), 
        Extension('astrid.workers', ['astrid/workers.c']), 
        Extension('astrid.names', ['astrid/names.c']), 
        Extension('astrid.mixer', ['astrid/mixer.c']), 
    ]


setup(
    name='astrid',
    version='1.0.0-alpha-1',
    description='Interactive computer music with Python',
    author='He Can Jog',
    author_email='erik@hecanjog.com',
    url='https://github.com/hecanjog/astrid',
    scripts = ['bin/astrid'],
    packages=['astrid'],
    ext_modules=ext_modules, 
)
