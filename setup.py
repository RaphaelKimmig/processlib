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
)
