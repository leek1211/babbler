from setuptools import setup

setup(
    name='creep',
    packages=['creep'],
    include_package_data=True,
    install_requires=[
        'flask', 'konlpy', 'jpype1', 'requests',
    ],
)
