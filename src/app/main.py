import logging
import os
import platform
import sys
import psutil

_logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):
    app_path = os.path.dirname(sys.executable)
    system_name = platform.system()

    if system_name == "Darwin":
        resdir = os.path.join(os.path.dirname(app_path), "Resources")
        os.environ["CRYNUX_SERVER_CONFIG"] = os.path.join(
            resdir, "config/config.yml")
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
        crynux_config.set_config(cfg)
        crynux_config.dump_config(cfg)
    else:
        error = RuntimeError(f"Unsupported platform: {system_name}")
        _logger.error(error)
        raise error
else:
    app_path = __file__
    for i in range(4):
        app_path = os.path.dirname(app_path)
    os.environ["CRYNUX_SERVER_CONFIG"] = os.path.join(app_path, "config/config.yml")

assert os.environ["CRYNUX_SERVER_CONFIG"]
_logger.info("Start Crynux Node from: ", app_path, os.environ["CRYNUX_SERVER_CONFIG"])


import asyncio
import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
import qasync

from anyio import run as anyio_run, create_task_group
from crynux_server.run import CrynuxRunner

class CrynuxApp(QWidget):

    def __init__(self, runner: CrynuxRunner):
        super().__init__()
        self.initUI()
        self.runner = runner

    def initUI(self):
        vbox = QVBoxLayout(self)
        self.webview = QWebEngineView()
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
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    async def _main():
        runner = CrynuxRunner()
        crynux_app = CrynuxApp(runner=runner)
        async with create_task_group() as tg:
            await tg.start(runner.run)
            await asyncio.sleep(delay=3.5)
            crynux_app.delayed_show()
    try:
        loop.create_task(_main())
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_default_executor())
        proc = psutil.Process(os.getpid())
        for p in proc.children(recursive=True):
            _logger.info(f"Kill process: {p.ppid()}, {p.cmdline()}")
            p.kill()
        proc.kill()


if __name__ == '__main__':
    main()