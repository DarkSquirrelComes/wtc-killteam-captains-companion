import pytest
from wtc_assistant.config import Configuration, Names
from wtc_assistant.solutions import PolicyBundle

@pytest.fixture(scope='session')
def config(fixed):
    return Configuration(fixed, Names.defaults())

@pytest.fixture(scope='session')
def bundle(config, complete):
    return PolicyBundle.create(config, complete['A'], complete['B'])
