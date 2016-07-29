from setuptools import setup, find_packages

execfile("oseoserver/version.py")

setup(
    name="django-oseoserver",
    version=__version__,
    description="A django app that implements the OGC ordering standard (OSEO)",
    long_description="",
    author="Ricardo Silva",
    author_email="ricardo.garcia.silva@gmail.com",
    url="",
    classifiers=[""],
    platforms=[""],
    license="",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "celery",
        "django",
        #"django-activity-stream",
        "django-mail-queue",
        "django-sendfile",
        "enum34",
        #"flower",
        "html2text",
        #"librabbitmq",
        "lxml",
        "pyxb",
        "redis",
    ],
)
