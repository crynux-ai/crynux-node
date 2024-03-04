import pytest

def pytest_addoption(parser):
    parser.addoption("--platform", type=str, action="store", default="cuda", help="cuda or macos")


def pytest_generate_tests(metafunc):
    platform = metafunc.config.getoption("--platform")
    if "use_cuda" in metafunc.fixturenames:
        metafunc.parametrize("use_cuda", [platform == "cuda"])
