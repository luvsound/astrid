#!/usr/bin/env python
from setuptools import setup

setup(
    name='astrid',
    version='1.0.0-alpha-1',
    description='Interactive computer music with Python',
    author='He Can Jog',
    author_email='erik@hecanjog.com',
    url='https://github.com/hecanjog/astrid',
    scripts = ['bin/astrid'],
    packages=['astrid'],
)
