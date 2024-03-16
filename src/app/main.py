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
        cfg.task_config.output_dir = os.path.join(resdir, "data/results")
        cfg.task_config.hf_cache_dir = os.path.join(resdir, "data/huggingface")
        cfg.task_config.external_cache_dir = os.path.join(resdir, "data/external")
        cfg.task_config.inference_logs_dir = os.path.join(resdir, "inference-logs")
        cfg.task_config.script_dir = os.path.join(resdir, "worker")
        crynux_config.set_config(cfg)
        crynux_config.dump_config(cfg)
    else:
        error = RuntimeError(f"Unsupported platform: {system_name}")
        _logger.error(error)
        raise error
else:
    app_path = os.path.dirname(__file__)

assert os.environ["CRYNUX_SERVER_CONFIG"]
_logger.info("Start Crynux Node from: ", app_path, os.environ["CRYNUX_SERVER_CONFIG"])


import asyncio
import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
import qasync

from crynux_server import run
from crynux_server import stop
import threading


class CrynuxApp(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        vbox = QVBoxLayout(self)
        self.webview = QWebEngineView()
        vbox.addWidget(self.webview)
        self.setLayout(vbox)
        self.setGeometry(300, 300, 1300, 700)
        self.setWindowTitle('Crynux Node')

    async def delayed_show(self, event):
        await event.wait()
        await asyncio.sleep(2)
        self.webview.load(QUrl("http://localhost:7412"))
        self.show()

    def closeEvent(self, event):
        loop = asyncio.get_running_loop()
        async def _close():
            run.server.stop()
            await run.node_manager.finish()
            stop.stop()

        task = loop.create_task(_close())
        task.add_done_callback(lambda t: event.accept())


def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    crynux_app = CrynuxApp()
    event = asyncio.Event()
    loop.create_task(run._run(event))
    loop.create_task(crynux_app.delayed_show(event))

    try:
        loop.run_forever()
    finally:
        loop.stop()
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()

    proc = psutil.Process(os.getpid())
    for p in proc.children(recursive=True):
      _logger.info(f"Kill process: {p.ppid()}, {p.cmdline()}")
      p.kill()
    proc.kill()


if __name__ == '__main__':
    main()