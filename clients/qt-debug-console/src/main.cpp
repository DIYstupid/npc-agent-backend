#include <QApplication>
#include <QFile>
#include <QIODevice>

#include "ui/MainWindow.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName("NPC Agent Debug Console");
    QApplication::setOrganizationName("npc-agent-backend");

    QFile themeFile(":/dark_theme.qss");
    if (themeFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        app.setStyleSheet(QString::fromUtf8(themeFile.readAll()));
    }

    MainWindow window;
    window.show();

    return app.exec();
}
