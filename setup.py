from setuptools import setup

setup(
    name="aurora-pricebot",
    version="1.0.0",
    py_modules=["bot", "prices"],
    install_requires=[
        "python-telegram-bot==21.4",
        "requests==2.32.3",
    ],
)
