from setuptools import setup

setup(
    name='babbler',
    packages=['babbler'],
    include_package_data=True,
    install_requires=[
        'flask', 'konlpy', 'jpype1',
    ],
)
