from setuptools import find_packages, setup


setup(
    name="smu-lit-audit",
    version="0.1.0",
    python_requires=">=3.9",
    packages=find_packages(include=["backend", "backend.*"]),
    install_requires=[
        "fastapi>=0.110,<1",
        "uvicorn[standard]>=0.29,<1",
        "pydantic>=2.5,<3",
        "python-dotenv>=1.0,<2",
    ],
)
