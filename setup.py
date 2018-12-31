import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Symbolic-File-System",
    version="2.0.0",
    url="",
    author="Rohit Biswas",
    author_email="biswasrohit143@gmail.com",
    description="Lightweight file manager for backing up and organizing your data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    python_requires='>=3',
    packages=setuptools.find_packages(exclude=['tests*']),
    entry_points={
        'console_scripts': [
            'sfs=sfs.cli:exec_cli'
        ]
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: System :: Filesystems",
        "Topic :: Utilities"
    ],
    keywords='symbolic-links file-system organize backup utility',
)
