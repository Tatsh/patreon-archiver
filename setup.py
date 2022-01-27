from setuptools import find_packages, setup

with open('README.md') as f:
    setup(author='Andrew Udvare',
          author_email='audvare@gmail.com',
          description='Archive Patreon content.',
          entry_points={
              'console_scripts': ['patreon-archiver = patreon_archiver:main']
          },
          extras_require={
              'dev': [
                  'mypy', 'mypy-extensions', 'pylint', 'rope',
                  'types-requests>=2.25.9'
              ]
          },
          install_requires=[
              'click>=8.0.0', 'loguru>=0.5.3', 'requests', 'yt-dlp'
          ],
          license='MIT',
          long_description=f.read(),
          long_description_content_type='text/markdown',
          name='patreon-archiver',
          packages=find_packages(),
          python_requires=">=3.9",
          url='https://github.com/Tatsh/patreon-archiver',
          version='0.0.5')
