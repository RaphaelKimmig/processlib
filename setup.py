from setuptools import setup, find_packages

setup(
    name="processlib",
    version="0.11.0",
    url="https://github.com/RaphaelKimmig/processlib",
    download_url="https://github.com/RaphaelKimmig/processlib/archive/0.11.0.tar.gz",
    author="Raphael Kimmig",
    author_email="raphael@ampad.de",
    description="A workflow library for python",
    include_package_data=True,
    packages=find_packages(),
    install_requires=[
        "django >= 3.2",
    ],
    classifiers=[
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Framework :: Django :: 5.1",
        "Framework :: Django :: 6.0",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
