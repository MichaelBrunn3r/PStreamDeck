from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='streamdeck',
    version='0.1',
    packages=find_packages(exclude=['tests*']),
    license=license,
    description='A python lib for the Elgato Stream Deck',
    long_description=readme,
    long_description_content_type='text/markdown',
    install_requires=['numpy','opencv-python','hidapi'],
    url='https://github.com/MichaelBrunn3r/PStreamDeck',
    author='Michael Brunner',
    author_email='MichaelBrunn3r@gmail.com'
)