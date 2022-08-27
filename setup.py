from setuptools import setup

setup(
    name='PyTractive',
    version='0.1',
    description='Python module and script to interact with the Tractive GPS tracker.',
    author='Dr. Usman Kayani',
    url='https://github.com/drrobotk/PyTractive',
    author_email='usman.kayaniphd@gmail.com',
    license='MIT',
    packages=['PyTractive'],
    install_requires=['geopy>=2.0', 'folium>=0.1', 'pandas>=1.0', 'Pillow>=8.0', 'pycrypto>=2.6', 'cryptography>=3.4'],
    include_package_data=True,
)
