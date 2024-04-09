import logging
import os
import platform
import sys
import psutil

_logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
dt_fmt = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
)
handler.setFormatter(formatter)
_logger.addHandler(handler)
_logger.setLevel(logging.DEBUG)


if getattr(sys, "frozen", False):
    app_path = os.path.dirname(sys.executable)
    system_name = platform.system()

    if system_name == "Darwin":
        resdir = os.path.join(os.path.dirname(app_path), "Resources")
        os.environ["CRYNUX_SERVER_CONFIG"] = os.path.join(resdir, "config", "config.yml")

        from crynux_server import config as crynux_config
        cfg = crynux_config.get_config()
        cfg.task_dir = os.path.join(resdir, "tasks")
        cfg.web_dist = os.path.join(resdir, "webui/dist")
        cfg.log.dir = os.path.join(resdir, "logs")
        cfg.db = f"sqlite+aiosqlite://{os.path.join(resdir, 'db/server.db')}"
        assert cfg.task_config is not None
        cfg.task_config.output_dir = os.path.join(resdir, "data/results")
        cfg.task_config.hf_cache_dir = os.path.join(resdir, "data/huggingface")
        cfg.task_config.external_cache_dir = os.path.join(resdir, "data/external")
        cfg.task_config.inference_logs_dir = os.path.join(resdir, "data/inference-logs")
        cfg.task_config.script_dir = os.path.join(resdir, "worker")
        cfg.task_config.resource_dir = os.path.join(resdir, "res")
        crynux_config.set_config(cfg)
        crynux_config.dump_config(cfg)

    elif system_name == "Windows":
        os.environ["CRYNUX_SERVER_CONFIG"] = os.path.join("config", "config.yml")
        from crynux_server import config as crynux_config

    else:
        error = RuntimeError(f"Unsupported platform: {system_name}")
        _logger.error(error)
        raise error

elif os.getenv("CRYNUX_SERVER_CONFIG") is None:
    index = __file__.rfind(os.path.sep + "src")
    root_dir = __file__[:index]

    os.environ["CRYNUX_SERVER_CONFIG"] = os.path.join(root_dir, "config", "config.yml")
    from crynux_server import config as crynux_config


assert os.environ["CRYNUX_SERVER_CONFIG"]
config_file_path = os.path.abspath(os.environ["CRYNUX_SERVER_CONFIG"])
_logger.info(f"Start Crynux Node from: {config_file_path}")


import asyncio
import sys
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
import qasync

from anyio import create_task_group, sleep
from crynux_server.run import CrynuxRunner


class CustomWebEnginePage(QWebEnginePage):

    def createWindow(self, _type):
        page = CustomWebEnginePage(self)
        page.urlChanged.connect(self.openBrowser)
        return page

    def openBrowser(self, url):
        page = self.sender()
        QDesktopServices.openUrl(url)
        page.deleteLater()


class CrynuxApp(QWidget):

    def __init__(self, runner: CrynuxRunner):
        super().__init__()
        _logger.debug("Initializing Application UI...")
        self.initUI()
        _logger.debug("Application UI initialized")
        self.runner = runner

    def initUI(self):

        vbox = QVBoxLayout(self)
        self.webview = QWebEngineView()
        self.webpage = CustomWebEnginePage()
        self.webview.setPage(self.webpage)

        settings = self.webpage.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
            True
        )

        vbox.addWidget(self.webview)
        self.setLayout(vbox)
        self.setGeometry(300, 300, 1300, 700)
        self.setWindowTitle('Crynux Node')

    def delayed_show(self):
        self.webview.load(QUrl("http://localhost:7412"))
        self.show()

    def closeEvent(self, event):
        loop = asyncio.get_running_loop()

        async def _close() -> None:
            await self.runner.stop()

        task = loop.create_task(_close())
        task.add_done_callback(lambda t: event.accept())


def main():
    _logger.info("Starting Crynux node...")
    app = QApplication(sys.argv)

    cfg = crynux_config.get_config()
    app.setWindowIcon(QIcon(os.path.join(cfg.resource_dir, "icon.ico")))

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    async def _main():
        _logger.debug("Creating runner and crynux_app")
        runner = CrynuxRunner()
        crynux_app = CrynuxApp(runner=runner)
        async with create_task_group() as tg:
            _logger.debug("Starting init task")
            await tg.start(runner.run)
            await sleep(3.5)
            _logger.debug("Starting the user interface")
            crynux_app.delayed_show()

    try:
        loop.create_task(_main())
        loop.run_forever()
    finally:
        proc = psutil.Process(os.getpid())
        for p in proc.children(recursive=True):
            _logger.info(f"Kill process: {p.ppid()}, {p.cmdline()}")
            p.kill()
        proc.kill()


if __name__ == '__main__':
    main()
