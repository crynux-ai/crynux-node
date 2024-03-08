import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget, QApplication, QVBoxLayout
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView


class CrynuxApp(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        vbox = QVBoxLayout(self)
        self.webview = QWebEngineView()
        self.webview.load(QUrl("http://localhost:7412"))
        vbox.addWidget(self.webview)
        self.setLayout(vbox)
        self.setGeometry(300, 300, 1300, 700)
        self.setWindowTitle('Crynux Node')
        self.show()

def main():
    app = QApplication(sys.argv)
    ex = CrynuxApp()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()