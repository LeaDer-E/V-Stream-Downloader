"""
Explicit literal imports of the entire Python Standard Library, submodules,
internal C/Python helper modules (like _markupbase, _strptime, _compression),
and yt-dlp / requests dependencies so PyInstaller AST/bytecode analysis
bundles 100% of required modules into the standalone executable.
"""
# ruff: noqa
# flake8: noqa

try:
    import __future__
except Exception:
    pass
try:
    import _abc
except Exception:
    pass
try:
    import _ast
except Exception:
    pass
try:
    import _bisect
except Exception:
    pass
try:
    import _blake2
except Exception:
    pass
try:
    import _bz2
except Exception:
    pass
try:
    import _codecs
except Exception:
    pass
try:
    import _codecs_cn
except Exception:
    pass
try:
    import _codecs_hk
except Exception:
    pass
try:
    import _codecs_iso2022
except Exception:
    pass
try:
    import _codecs_jp
except Exception:
    pass
try:
    import _codecs_kr
except Exception:
    pass
try:
    import _codecs_tw
except Exception:
    pass
try:
    import _collections
except Exception:
    pass
try:
    import _collections_abc
except Exception:
    pass
try:
    import _compat_pickle
except Exception:
    pass
try:
    import _compression
except Exception:
    pass
try:
    import _contextvars
except Exception:
    pass
try:
    import _csv
except Exception:
    pass
try:
    import _ctypes
except Exception:
    pass
try:
    import _datetime
except Exception:
    pass
try:
    import _decimal
except Exception:
    pass
try:
    import _elementtree
except Exception:
    pass
try:
    import _functools
except Exception:
    pass
try:
    import _hashlib
except Exception:
    pass
try:
    import _heapq
except Exception:
    pass
try:
    import _imp
except Exception:
    pass
try:
    import _io
except Exception:
    pass
try:
    import _json
except Exception:
    pass
try:
    import _locale
except Exception:
    pass
try:
    import _lsprof
except Exception:
    pass
try:
    import _lzma
except Exception:
    pass
try:
    import _markupbase
except Exception:
    pass
try:
    import _md5
except Exception:
    pass
try:
    import _multibytecodec
except Exception:
    pass
try:
    import _multiprocessing
except Exception:
    pass
try:
    import _opcode
except Exception:
    pass
try:
    import _operator
except Exception:
    pass
try:
    import _pickle
except Exception:
    pass
try:
    import _py_abc
except Exception:
    pass
try:
    import _pydecimal
except Exception:
    pass
try:
    import _pyio
except Exception:
    pass
try:
    import _queue
except Exception:
    pass
try:
    import _random
except Exception:
    pass
try:
    import _sha1
except Exception:
    pass
try:
    import _sha256
except Exception:
    pass
try:
    import _sha3
except Exception:
    pass
try:
    import _sha512
except Exception:
    pass
try:
    import _signal
except Exception:
    pass
try:
    import _sitebuiltins
except Exception:
    pass
try:
    import _socket
except Exception:
    pass
try:
    import _sqlite3
except Exception:
    pass
try:
    import _sre
except Exception:
    pass
try:
    import _ssl
except Exception:
    pass
try:
    import _stat
except Exception:
    pass
try:
    import _statistics
except Exception:
    pass
try:
    import _string
except Exception:
    pass
try:
    import _strptime
except Exception:
    pass
try:
    import _struct
except Exception:
    pass
try:
    import _symtable
except Exception:
    pass
try:
    import _thread
except Exception:
    pass
try:
    import _threading_local
except Exception:
    pass
try:
    import _tokenize
except Exception:
    pass
try:
    import _tracemalloc
except Exception:
    pass
try:
    import _typing
except Exception:
    pass
try:
    import _uuid
except Exception:
    pass
try:
    import _warnings
except Exception:
    pass
try:
    import _weakref
except Exception:
    pass
try:
    import _weakrefset
except Exception:
    pass
try:
    import abc
except Exception:
    pass
try:
    import argparse
except Exception:
    pass
try:
    import array
except Exception:
    pass
try:
    import ast
except Exception:
    pass
try:
    import asyncio
except Exception:
    pass
try:
    import asyncio.base_events
except Exception:
    pass
try:
    import asyncio.base_futures
except Exception:
    pass
try:
    import asyncio.base_subprocess
except Exception:
    pass
try:
    import asyncio.base_tasks
except Exception:
    pass
try:
    import asyncio.constants
except Exception:
    pass
try:
    import asyncio.coroutines
except Exception:
    pass
try:
    import asyncio.events
except Exception:
    pass
try:
    import asyncio.exceptions
except Exception:
    pass
try:
    import asyncio.format_helpers
except Exception:
    pass
try:
    import asyncio.futures
except Exception:
    pass
try:
    import asyncio.locks
except Exception:
    pass
try:
    import asyncio.log
except Exception:
    pass
try:
    import asyncio.mixins
except Exception:
    pass
try:
    import asyncio.protocols
except Exception:
    pass
try:
    import asyncio.queues
except Exception:
    pass
try:
    import asyncio.runners
except Exception:
    pass
try:
    import asyncio.selector_events
except Exception:
    pass
try:
    import asyncio.sslproto
except Exception:
    pass
try:
    import asyncio.staggered
except Exception:
    pass
try:
    import asyncio.streams
except Exception:
    pass
try:
    import asyncio.subprocess
except Exception:
    pass
try:
    import asyncio.tasks
except Exception:
    pass
try:
    import asyncio.threads
except Exception:
    pass
try:
    import asyncio.transports
except Exception:
    pass
try:
    import asyncio.trsock
except Exception:
    pass
try:
    import atexit
except Exception:
    pass
try:
    import base64
except Exception:
    pass
try:
    import bdb
except Exception:
    pass
try:
    import binascii
except Exception:
    pass
try:
    import bisect
except Exception:
    pass
try:
    import builtins
except Exception:
    pass
try:
    import bz2
except Exception:
    pass
try:
    import calendar
except Exception:
    pass
try:
    import cmath
except Exception:
    pass
try:
    import cmd
except Exception:
    pass
try:
    import code
except Exception:
    pass
try:
    import codecs
except Exception:
    pass
try:
    import codeop
except Exception:
    pass
try:
    import collections
except Exception:
    pass
try:
    import collections.abc
except Exception:
    pass
try:
    import colorsys
except Exception:
    pass
try:
    import compileall
except Exception:
    pass
try:
    import concurrent
except Exception:
    pass
try:
    import concurrent.futures
except Exception:
    pass
try:
    import concurrent.futures.process
except Exception:
    pass
try:
    import concurrent.futures.thread
except Exception:
    pass
try:
    import configparser
except Exception:
    pass
try:
    import contextlib
except Exception:
    pass
try:
    import contextvars
except Exception:
    pass
try:
    import copy
except Exception:
    pass
try:
    import copyreg
except Exception:
    pass
try:
    import cProfile
except Exception:
    pass
try:
    import csv
except Exception:
    pass
try:
    import ctypes
except Exception:
    pass
try:
    import ctypes.util
except Exception:
    pass
try:
    import dataclasses
except Exception:
    pass
try:
    import datetime
except Exception:
    pass
try:
    import decimal
except Exception:
    pass
try:
    import difflib
except Exception:
    pass
try:
    import dis
except Exception:
    pass
try:
    import doctest
except Exception:
    pass
try:
    import email
except Exception:
    pass
try:
    import email.base64mime
except Exception:
    pass
try:
    import email.charset
except Exception:
    pass
try:
    import email.contentmanager
except Exception:
    pass
try:
    import email.encoders
except Exception:
    pass
try:
    import email.errors
except Exception:
    pass
try:
    import email.feedparser
except Exception:
    pass
try:
    import email.generator
except Exception:
    pass
try:
    import email.header
except Exception:
    pass
try:
    import email.headerregistry
except Exception:
    pass
try:
    import email.iterators
except Exception:
    pass
try:
    import email.message
except Exception:
    pass
try:
    import email.mime
except Exception:
    pass
try:
    import email.mime.application
except Exception:
    pass
try:
    import email.mime.audio
except Exception:
    pass
try:
    import email.mime.base
except Exception:
    pass
try:
    import email.mime.image
except Exception:
    pass
try:
    import email.mime.message
except Exception:
    pass
try:
    import email.mime.multipart
except Exception:
    pass
try:
    import email.mime.nonmultipart
except Exception:
    pass
try:
    import email.mime.text
except Exception:
    pass
try:
    import email.parser
except Exception:
    pass
try:
    import email.policy
except Exception:
    pass
try:
    import email.quoprimime
except Exception:
    pass
try:
    import email.utils
except Exception:
    pass
try:
    import encodings
except Exception:
    pass
try:
    import encodings.aliases
except Exception:
    pass
try:
    import encodings.ascii
except Exception:
    pass
try:
    import encodings.base64_codec
except Exception:
    pass
try:
    import encodings.charmap
except Exception:
    pass
try:
    import encodings.cp1252
except Exception:
    pass
try:
    import encodings.cp1256
except Exception:
    pass
try:
    import encodings.cp437
except Exception:
    pass
try:
    import encodings.cp65001
except Exception:
    pass
try:
    import encodings.hex_codec
except Exception:
    pass
try:
    import encodings.idna
except Exception:
    pass
try:
    import encodings.latin_1
except Exception:
    pass
try:
    import encodings.mbcs
except Exception:
    pass
try:
    import encodings.punycode
except Exception:
    pass
try:
    import encodings.raw_unicode_escape
except Exception:
    pass
try:
    import encodings.unicode_escape
except Exception:
    pass
try:
    import encodings.utf_16
except Exception:
    pass
try:
    import encodings.utf_16_be
except Exception:
    pass
try:
    import encodings.utf_16_le
except Exception:
    pass
try:
    import encodings.utf_32
except Exception:
    pass
try:
    import encodings.utf_32_be
except Exception:
    pass
try:
    import encodings.utf_32_le
except Exception:
    pass
try:
    import encodings.utf_7
except Exception:
    pass
try:
    import encodings.utf_8
except Exception:
    pass
try:
    import encodings.utf_8_sig
except Exception:
    pass
try:
    import enum
except Exception:
    pass
try:
    import errno
except Exception:
    pass
try:
    import faulthandler
except Exception:
    pass
try:
    import filecmp
except Exception:
    pass
try:
    import fileinput
except Exception:
    pass
try:
    import fnmatch
except Exception:
    pass
try:
    import fractions
except Exception:
    pass
try:
    import ftplib
except Exception:
    pass
try:
    import functools
except Exception:
    pass
try:
    import gc
except Exception:
    pass
try:
    import genericpath
except Exception:
    pass
try:
    import getopt
except Exception:
    pass
try:
    import getpass
except Exception:
    pass
try:
    import gettext
except Exception:
    pass
try:
    import glob
except Exception:
    pass
try:
    import graphlib
except Exception:
    pass
try:
    import gzip
except Exception:
    pass
try:
    import hashlib
except Exception:
    pass
try:
    import heapq
except Exception:
    pass
try:
    import hmac
except Exception:
    pass
try:
    import html
except Exception:
    pass
try:
    import html.entities
except Exception:
    pass
try:
    import html.parser
except Exception:
    pass
try:
    import http
except Exception:
    pass
try:
    import http.client
except Exception:
    pass
try:
    import http.cookiejar
except Exception:
    pass
try:
    import http.cookies
except Exception:
    pass
try:
    import http.server
except Exception:
    pass
try:
    import imaplib
except Exception:
    pass
try:
    import importlib
except Exception:
    pass
try:
    import importlib.abc
except Exception:
    pass
try:
    import importlib.machinery
except Exception:
    pass
try:
    import importlib.metadata
except Exception:
    pass
try:
    import importlib.resources
except Exception:
    pass
try:
    import importlib.util
except Exception:
    pass
try:
    import inspect
except Exception:
    pass
try:
    import io
except Exception:
    pass
try:
    import ipaddress
except Exception:
    pass
try:
    import itertools
except Exception:
    pass
try:
    import json
except Exception:
    pass
try:
    import keyword
except Exception:
    pass
try:
    import linecache
except Exception:
    pass
try:
    import locale
except Exception:
    pass
try:
    import logging
except Exception:
    pass
try:
    import logging.config
except Exception:
    pass
try:
    import logging.handlers
except Exception:
    pass
try:
    import lzma
except Exception:
    pass
try:
    import mailbox
except Exception:
    pass
try:
    import marshal
except Exception:
    pass
try:
    import math
except Exception:
    pass
try:
    import mimetypes
except Exception:
    pass
try:
    import mmap
except Exception:
    pass
try:
    import modulefinder
except Exception:
    pass
try:
    import multiprocessing
except Exception:
    pass
try:
    import multiprocessing.connection
except Exception:
    pass
try:
    import multiprocessing.context
except Exception:
    pass
try:
    import multiprocessing.dummy
except Exception:
    pass
try:
    import multiprocessing.dummy.connection
except Exception:
    pass
try:
    import multiprocessing.heap
except Exception:
    pass
try:
    import multiprocessing.managers
except Exception:
    pass
try:
    import multiprocessing.pool
except Exception:
    pass
try:
    import multiprocessing.process
except Exception:
    pass
try:
    import multiprocessing.queues
except Exception:
    pass
try:
    import multiprocessing.reduction
except Exception:
    pass
try:
    import multiprocessing.resource_sharer
except Exception:
    pass
try:
    import multiprocessing.resource_tracker
except Exception:
    pass
try:
    import multiprocessing.shared_memory
except Exception:
    pass
try:
    import multiprocessing.sharedctypes
except Exception:
    pass
try:
    import multiprocessing.spawn
except Exception:
    pass
try:
    import multiprocessing.synchronize
except Exception:
    pass
try:
    import multiprocessing.util
except Exception:
    pass
try:
    import netrc
except Exception:
    pass
try:
    import ntpath
except Exception:
    pass
try:
    import nturl2path
except Exception:
    pass
try:
    import numbers
except Exception:
    pass
try:
    import opcode
except Exception:
    pass
try:
    import operator
except Exception:
    pass
try:
    import optparse
except Exception:
    pass
try:
    import os
except Exception:
    pass
try:
    import pathlib
except Exception:
    pass
try:
    import pdb
except Exception:
    pass
try:
    import pickle
except Exception:
    pass
try:
    import pickletools
except Exception:
    pass
try:
    import pkgutil
except Exception:
    pass
try:
    import platform
except Exception:
    pass
try:
    import plistlib
except Exception:
    pass
try:
    import poplib
except Exception:
    pass
try:
    import posixpath
except Exception:
    pass
try:
    import pprint
except Exception:
    pass
try:
    import profile
except Exception:
    pass
try:
    import pstats
except Exception:
    pass
try:
    import py_compile
except Exception:
    pass
try:
    import pyclbr
except Exception:
    pass
try:
    import pydoc
except Exception:
    pass
try:
    import pyexpat
except Exception:
    pass
try:
    import queue
except Exception:
    pass
try:
    import quopri
except Exception:
    pass
try:
    import random
except Exception:
    pass
try:
    import re
except Exception:
    pass
try:
    import reprlib
except Exception:
    pass
try:
    import rlcompleter
except Exception:
    pass
try:
    import runpy
except Exception:
    pass
try:
    import sched
except Exception:
    pass
try:
    import secrets
except Exception:
    pass
try:
    import select
except Exception:
    pass
try:
    import selectors
except Exception:
    pass
try:
    import shelve
except Exception:
    pass
try:
    import shlex
except Exception:
    pass
try:
    import shutil
except Exception:
    pass
try:
    import signal
except Exception:
    pass
try:
    import site
except Exception:
    pass
try:
    import smtplib
except Exception:
    pass
try:
    import socket
except Exception:
    pass
try:
    import socketserver
except Exception:
    pass
try:
    import sqlite3
except Exception:
    pass
try:
    import sre_compile
except Exception:
    pass
try:
    import sre_constants
except Exception:
    pass
try:
    import sre_parse
except Exception:
    pass
try:
    import ssl
except Exception:
    pass
try:
    import stat
except Exception:
    pass
try:
    import statistics
except Exception:
    pass
try:
    import string
except Exception:
    pass
try:
    import stringprep
except Exception:
    pass
try:
    import struct
except Exception:
    pass
try:
    import subprocess
except Exception:
    pass
try:
    import symtable
except Exception:
    pass
try:
    import sys
except Exception:
    pass
try:
    import sysconfig
except Exception:
    pass
try:
    import tabnanny
except Exception:
    pass
try:
    import tarfile
except Exception:
    pass
try:
    import tempfile
except Exception:
    pass
try:
    import textwrap
except Exception:
    pass
try:
    import threading
except Exception:
    pass
try:
    import time
except Exception:
    pass
try:
    import timeit
except Exception:
    pass
try:
    import token
except Exception:
    pass
try:
    import tokenize
except Exception:
    pass
try:
    import trace
except Exception:
    pass
try:
    import traceback
except Exception:
    pass
try:
    import tracemalloc
except Exception:
    pass
try:
    import types
except Exception:
    pass
try:
    import typing
except Exception:
    pass
try:
    import unicodedata
except Exception:
    pass
try:
    import unittest
except Exception:
    pass
try:
    import unittest.async_case
except Exception:
    pass
try:
    import unittest.case
except Exception:
    pass
try:
    import unittest.loader
except Exception:
    pass
try:
    import unittest.main
except Exception:
    pass
try:
    import unittest.mock
except Exception:
    pass
try:
    import unittest.result
except Exception:
    pass
try:
    import unittest.runner
except Exception:
    pass
try:
    import unittest.signals
except Exception:
    pass
try:
    import unittest.suite
except Exception:
    pass
try:
    import unittest.util
except Exception:
    pass
try:
    import urllib
except Exception:
    pass
try:
    import urllib.error
except Exception:
    pass
try:
    import urllib.parse
except Exception:
    pass
try:
    import urllib.request
except Exception:
    pass
try:
    import urllib.response
except Exception:
    pass
try:
    import urllib.robotparser
except Exception:
    pass
try:
    import uuid
except Exception:
    pass
try:
    import warnings
except Exception:
    pass
try:
    import wave
except Exception:
    pass
try:
    import weakref
except Exception:
    pass
try:
    import webbrowser
except Exception:
    pass
try:
    import wsgiref
except Exception:
    pass
try:
    import wsgiref.handlers
except Exception:
    pass
try:
    import wsgiref.headers
except Exception:
    pass
try:
    import wsgiref.simple_server
except Exception:
    pass
try:
    import wsgiref.types
except Exception:
    pass
try:
    import wsgiref.util
except Exception:
    pass
try:
    import wsgiref.validate
except Exception:
    pass
try:
    import xml
except Exception:
    pass
try:
    import xml.dom
except Exception:
    pass
try:
    import xml.dom.NodeFilter
except Exception:
    pass
try:
    import xml.dom.domreg
except Exception:
    pass
try:
    import xml.dom.expatbuilder
except Exception:
    pass
try:
    import xml.dom.minicompat
except Exception:
    pass
try:
    import xml.dom.minidom
except Exception:
    pass
try:
    import xml.dom.pulldom
except Exception:
    pass
try:
    import xml.dom.xmlbuilder
except Exception:
    pass
try:
    import xml.etree
except Exception:
    pass
try:
    import xml.etree.ElementInclude
except Exception:
    pass
try:
    import xml.etree.ElementPath
except Exception:
    pass
try:
    import xml.etree.ElementTree
except Exception:
    pass
try:
    import xml.etree.cElementTree
except Exception:
    pass
try:
    import xml.parsers
except Exception:
    pass
try:
    import xml.parsers.expat
except Exception:
    pass
try:
    import xml.sax
except Exception:
    pass
try:
    import xml.sax.expatreader
except Exception:
    pass
try:
    import xml.sax.handler
except Exception:
    pass
try:
    import xml.sax.saxutils
except Exception:
    pass
try:
    import xml.sax.xmlreader
except Exception:
    pass
try:
    import xmlrpc
except Exception:
    pass
try:
    import xmlrpc.client
except Exception:
    pass
try:
    import xmlrpc.server
except Exception:
    pass
try:
    import zipapp
except Exception:
    pass
try:
    import zipfile
except Exception:
    pass
try:
    import zipimport
except Exception:
    pass
try:
    import zlib
except Exception:
    pass
try:
    import tomllib
except Exception:
    pass
try:
    import zoneinfo
except Exception:
    pass
try:
    import _zoneinfo
except Exception:
    pass
try:
    import asyncio.taskgroups
except Exception:
    pass
try:
    import asyncio.timeouts
except Exception:
    pass
try:
    import asyncio.proactor_events
except Exception:
    pass
try:
    import asyncio.windows_events
except Exception:
    pass
try:
    import asyncio.windows_utils
except Exception:
    pass
try:
    import multiprocessing.popen_spawn_win32
except Exception:
    pass
try:
    import ctypes.wintypes
except Exception:
    pass
try:
    import msvcrt
except Exception:
    pass
try:
    import winreg
except Exception:
    pass
try:
    import winsound
except Exception:
    pass
try:
    import _winapi
except Exception:
    pass
try:
    import _overlapped
except Exception:
    pass
try:
    import _msi
except Exception:
    pass
try:
    import cgi
except Exception:
    pass
try:
    import cgitb
except Exception:
    pass
try:
    import chunk
except Exception:
    pass
try:
    import imghdr
except Exception:
    pass
try:
    import mailcap
except Exception:
    pass
try:
    import nntplib
except Exception:
    pass
try:
    import pipes
except Exception:
    pass
try:
    import sndhdr
except Exception:
    pass
try:
    import sunau
except Exception:
    pass
try:
    import telnetlib
except Exception:
    pass
try:
    import uu
except Exception:
    pass
try:
    import xdrlib
except Exception:
    pass
try:
    import audioop
except Exception:
    pass
try:
    import aifc
except Exception:
    pass
try:
    import asynchat
except Exception:
    pass
try:
    import asyncore
except Exception:
    pass
try:
    import smtpd
except Exception:
    pass
try:
    import certifi
except Exception:
    pass
try:
    import urllib3
except Exception:
    pass
try:
    import idna
except Exception:
    pass
try:
    import charset_normalizer
except Exception:
    pass
try:
    import requests
except Exception:
    pass
try:
    import socks
except Exception:
    pass
try:
    import websockets
except Exception:
    pass
try:
    import mutagen
except Exception:
    pass
try:
    import brotli
except Exception:
    pass
try:
    import yt_dlp
except Exception:
    pass
try:
    import yt_dlp.version
except Exception:
    pass
try:
    import yt_dlp.options
except Exception:
    pass
try:
    import yt_dlp.utils
except Exception:
    pass
try:
    import yt_dlp.cookies
except Exception:
    pass
try:
    import yt_dlp.aes
except Exception:
    pass
try:
    import yt_dlp.networking
except Exception:
    pass
try:
    import yt_dlp.downloader
except Exception:
    pass
try:
    import yt_dlp.postprocessor
except Exception:
    pass
try:
    import yt_dlp.extractor
except Exception:
    pass
try:
    import yt_dlp.compat
except Exception:
    pass
try:
    import yt_dlp_ejs
except Exception:
    pass
