#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path

from pkg_resources import parse_requirements
from setuptools import setup

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README.md')
readme = open(README).read()

install_requires = None
with open("requirements.txt") as reqs:
    install_reqs = parse_requirements(reqs)
    install_requires = [str(r) for r in install_reqs]

setup(
    name='regate',
    version='1.0.0_beta',
    description='Registration of Galaxy Tools in Elixir',
    long_description=readme,
    keywords=['GalaxyProject'],
    author='Olivia Doppelt-Azeroual and Fabien Mareuil',
    author_email='olivia.doppelt@pasteur.fr and fabien.mareuil@pasteur.fr',
    url='https://github.com/bioinfo-center-pasteur-fr/ReGaTE',
    packages=['regate', 'regate.cli'],
    install_requires=install_requires,
    license="GPLv2",
    entry_points={
        'console_scripts': ['regate=regate.cli.regate:run',
                            'remag=regate.cli.remag:run'],
    },
    tests_require=['nose', 'nose_parameterized'],
    test_suite='nose.collector',
    include_package_data=True,
    zip_safe=False
)
