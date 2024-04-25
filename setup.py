import pathlib
from setuptools import setup, find_packages

pkg_name = "kunkin"

# Get version
exec(open(pathlib.Path("src") / pkg_name / "version.py").read())

setup(
    name=pkg_name,
    version=__version__,
    url="https://github.com/korjaa/kunkin-kp184",
    author="Jaakko Korhonen",
    description="Kunkin KP184 Driver.",
    packages=find_packages("src"),
    package_dir={"": "src"},
    #entry_points={
    #    "console_scripts": [
    #        f"{pkg_name}={pkg_name}.cli:main"
    #    ]
    #},
    install_requires=[
        "pyserial ~= 3.5",
        "tenacity ~= 8.2"
    ],
)
