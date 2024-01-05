import pytest

def pytest_addoption(parser):
    parser.addoption("--gpu", action="store_true", help="run tests with gpu")


def pytest_generate_tests(metafunc):
    if "enable_gpu" in metafunc.fixturenames:
        metafunc.parametrize("enable_gpu", [metafunc.config.getoption("--gpu")])
