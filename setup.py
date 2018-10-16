from setuptools import setup, find_packages

setup(
    name='processlib',
    version='0.5.5',
    url='https://github.com/RaphaelKimmig/processlib',
    download_url='https://github.com/RaphaelKimmig/processlib/archive/0.5.5.tar.gz',
    author='Raphael Kimmig',
    author_email='raphael@ampad.de',
    description='A workflow library for python',
    packages=find_packages(),
    install_requires=['django >= 1.10', ],
)
