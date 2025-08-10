"""
Setup configuration for PyTractive.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "PyTractive" / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = requirements_file.read_text(encoding="utf-8").strip().split("\n")
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith("#")]

setup(
    name="PyTractive",
    version="1.0.0",
    description="Modern Python library for Tractive GPS pet trackers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Dr. Usman Kayani",
    author_email="usman.kayaniphd@gmail.com",
    url="https://github.com/drrobotk/PyTractive",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests>=2.25.0",
        "cryptography>=3.4.0",
        "pandas>=1.3.0",
        "click>=8.0.0",
        "folium>=0.12.0",
        "geopy>=2.0.0",
        "pillow>=8.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=21.0.0",
            "flake8>=3.8.0",
            "mypy>=0.800",
            "pre-commit>=2.10.0",
        ],
        "cli": [
            "click>=8.0.0",
            "folium>=0.12.0",
            "geopy>=2.0.0",
            "pillow>=8.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "pytractive=PyTractive.cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    keywords="tractive gps pet tracker api client",
    project_urls={
        "Bug Reports": "https://github.com/drrobotk/PyTractive/issues",
        "Source": "https://github.com/drrobotk/PyTractive",
        "Documentation": "https://github.com/drrobotk/PyTractive/blob/main/README.md",
    },
)
