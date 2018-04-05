#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='bloom_homebrew',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    include_package_data=True,
    install_requires=[
        'argparse',
        'catkin-pkg >= 0.1.14',
        'empy',
        'python-dateutil',
        'bloom >= 0.4.4',
    ],
    author='William Woodall',
    author_email='william@osrfoundation.org',
    maintainer='William Woodall',
    maintainer_email='william@osrfoundation.org',
    url='https://github.com/wjwwood/bloom_homebrew',
    keywords=['ROS', 'Homebrew'],
    classifiers=['Programming Language :: Python',
                 'License :: OSI Approved :: BSD License'],
    description="Homebrew (mac package manager) support for bloom.",
    long_description="""Generates Homebrew Formulae for catkin packages.""",
    license='MIT',
    entry_points={
        'bloom.generators': [],
        'bloom.generate_cmds': [
            'homebrew = bloom_homebrew.generate_cmd:description'
#,
#            'roshomebrew = bloom_homebrew.ros_generate_cmd:description'
        ]
    }
)
