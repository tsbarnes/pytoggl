#!/usr/bin/env python

from setuptools import setup, find_packages

version = '0.1.0'

setup(
    name='pytoggl',
    version=version,
    description="Toggl API module for Python.",
    long_description=open("README.md", "r").read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
    ],
    keywords='toggl',
    author='T. Scott Barnes',
    author_email='barnes.t.scott@gmail.com',
    url='http://github.com/tsbarnes/pytoggl',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'iso8601>=0.1',
        'pytz>=2014.10',
        'requests>=2.5',
    ],
)
