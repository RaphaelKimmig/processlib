from setuptools import setup, find_packages

setup(
    name='processlib',
    version='0.0.1',
    url='https://github.com/RaphaelKimmig/processlib',
    download_url='https://github.com/RaphaelKimmig/processlib/archive/0.0.1.tar.gz',
    author='Raphael Kimmig',
    author_email='raphael@ampad.de',
    description='A workflow library for python',
    packages=find_packages(),
    install_requires=['django >= 1.8', ],
)