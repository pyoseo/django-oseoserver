#!/usr/bin/env python

import io
from os.path import dirname, join

from setuptools import find_packages, setup


def read(*names, **kwargs):
    return io.open(
        join(dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf-8")
    ).read()


setup(
    name="oseoserver",
    version=read("VERSION"),
    description="A django app that implements the OGC ordering standard (OSEO)",
    long_description="",
    author="Ricardo Silva",
    author_email="ricardo.garcia.silva@gmail.com",
    url="https://github.com/pyoseo/django-oseoserver",
    classifiers=[""],
    platforms=[""],
    license="apache",
    packages=find_packages(),
    include_package_data=True,
    entry_points= {
        "console_scripts": [
            "install_pyxb_ogc_bindings=oseoserver.scripts.install_pyxb_ogc_bindings:main"
        ],
    },
    install_requires=[
        "celery",
        "django",
        "django-mail-queue",
        "django-sendfile",
        "enum34",
        "html2text",
        "lxml",
        "pyxb",
        "redis",
    ],
)
