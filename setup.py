from setuptools import setup

with open('README.md') as f:
    setup(author='Andrew Udvare',
          author_email='audvare@gmail.com',
          description='Command line utilities for interfacing with Xirvik.',
          entry_points={
              'console_scripts': ['patreon-archiver = patreon_archiver:main']
          },
          extras_require={
              'dev': [
                  'mypy', 'mypy-extensions', 'pylint', 'rope',
                  'types-requests>=2.25.9'
              ]
          },
          install_requires=['click', 'requests', 'yt-dlp'],
          license='LICENSE.txt',
          long_description=f.read(),
          name='patreon-archiver',
          url='https://github.com/Tatsh/patreon-archiver',
          version='0.0.1')
