from setuptools import setup

# 读取 requirements.txt
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="AVJPWConverterPyQt5",
    version="1.0",
    py_modules=["AVJPWConverterPyQt5"],
    install_requires=requirements,
    python_requires=">=3.10",
)
