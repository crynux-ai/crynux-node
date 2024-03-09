import asyncio
import sys
from PyQt6.QtCore import QUrl, QThread, pyqtSlot, QObject
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
import qasync

from crynux_server import run
from crynux_server import stop



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
    except KeyboardInterrupt:
        pass
    finally:
        loop.stop()
        sys.exit(app.exec())


if __name__ == '__main__':
    main()