import os
import pathlib

import setuptools
import setuptools.command.build_py
import setuptools.command.install
import setuptools.command.sdist

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")


setuptools.setup(
    name="ygojson",
    version="0.1.0",
    description="Generate and manipulate Yugioh card and set data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iconmaster5326/YGOJSON",
    author="iconmaster5326",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="yugioh,ygo,ygojson",
    packages=setuptools.find_packages(),
    py_modules=[],
    python_requires=">=3.8, <4",
    install_requires=["requests", "wikitextparser"],
    extras_require={
        "dev": ["pre-commit"],
        "test": [],
    },
    package_data={
        "ygojson": [],
    },
    entry_points={
        "console_scripts": [
            "ygojson=ygojson:main",
        ],
    },
)
