import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="python_v2ray",
    version="0.1.0",
    author="Arshia",
    author_email="arshiacomplus@gmail.com",
    description="A powerful, high-level Python wrapper for managing and testing V2Ray/Xray-core and Hysteria clients.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/arshiacomplus/python_v2ray",
    license="GPL-3.0-only",
    packages=setuptools.find_packages(),
    package_data={
        "python_v2ray": [
            "vendor/*",
            "core_engine/*",
        ],
    },
    install_requires=[
        "requests",
        "grpcio",
        "protobuf",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: System :: Networking",
    ],

    python_requires=">=3.8",
)