import json


def normalize(name: str) -> str:
    return name.strip().lower()


async def load_user(name: str):
    key = normalize(name)
    return external_client.fetch(key)


def entry(name: str):
    return load_user(name)
