#include "MainWindow.h"

#include <QCloseEvent>
#include <QComboBox>
#include <QDockWidget>
#include <QGuiApplication>
#include <QLineEdit>
#include <QList>
#include <QRect>
#include <QScreen>
#include <QSize>
#include <QSplitter>
#include <QTimer>
#include <QtGlobal>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
{
    streamingRenderTimer_ = new QTimer(this);
    streamingRenderTimer_->setInterval(25);
    connect(streamingRenderTimer_, &QTimer::timeout, this, &MainWindow::renderNextStreamingChatCharacter);

    setupUi();
    applyDefaultWindowGeometry();
    applyDefaultDockLayout();
    loadPersistentSettings();
    connectSignals();
    updateRequestControls();
    refreshAll(false);
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    savePersistentSettings();
    QMainWindow::closeEvent(event);
}

void MainWindow::applyDefaultWindowGeometry()
{
    const QScreen *screen = QGuiApplication::primaryScreen();
    if (!screen) {
        setMinimumSize(900, 620);
        resize(1280, 800);
        return;
    }

    const QRect available = screen->availableGeometry();
    const int maxWidth = qMax(720, available.width() - 40);
    const int maxHeight = qMax(520, available.height() - 40);
    const int minWidth = qMin(900, maxWidth);
    const int minHeight = qMin(620, maxHeight);
    const int preferredWidth = qMin(1440, qMax(minWidth, available.width() * 86 / 100));
    const int preferredHeight = qMin(920, qMax(minHeight, available.height() * 86 / 100));
    const int windowWidth = qMin(maxWidth, preferredWidth);
    const int windowHeight = qMin(maxHeight, preferredHeight);

    setMinimumSize(minWidth, minHeight);
    resize(windowWidth, windowHeight);
    move(
        available.left() + (available.width() - windowWidth) / 2,
        available.top() + (available.height() - windowHeight) / 2);
}

void MainWindow::applyDefaultDockLayout()
{
    if (!contextDock_
        || !actionsDock_
        || !memoryDock_
        || !traceDock_
        || !questDock_
        || !worldActionDock_
        || !worldEventsDock_
        || !statusDock_) {
        return;
    }

    QList<QDockWidget *> rightDocks;
    rightDocks << contextDock_ << actionsDock_ << questDock_ << worldActionDock_ << worldEventsDock_ << memoryDock_ << traceDock_;
    for (QDockWidget *dock : rightDocks) {
        dock->setFloating(false);
        dock->show();
        addDockWidget(Qt::RightDockWidgetArea, dock);
    }

    statusDock_->setFloating(false);
    statusDock_->show();
    addDockWidget(Qt::BottomDockWidgetArea, statusDock_);

    tabifyDockWidget(contextDock_, actionsDock_);
    tabifyDockWidget(contextDock_, questDock_);
    tabifyDockWidget(contextDock_, worldActionDock_);
    tabifyDockWidget(contextDock_, worldEventsDock_);
    tabifyDockWidget(contextDock_, memoryDock_);
    tabifyDockWidget(contextDock_, traceDock_);
    contextDock_->raise();

    if (mainSplitter_) {
        QList<int> sizes;
        sizes << 360 << 620;
        mainSplitter_->setSizes(sizes);
    }

    QList<int> rightDockWidth;
    rightDockWidth << 420;
    QList<QDockWidget *> rightDockResizeTargets;
    rightDockResizeTargets << contextDock_;
    resizeDocks(rightDockResizeTargets, rightDockWidth, Qt::Horizontal);

    QList<int> statusDockHeight;
    statusDockHeight << 120;
    QList<QDockWidget *> statusDockResizeTargets;
    statusDockResizeTargets << statusDock_;
    resizeDocks(statusDockResizeTargets, statusDockHeight, Qt::Vertical);
}

void MainWindow::resetLayoutToDefault()
{
    applyDefaultWindowGeometry();
    applyDefaultDockLayout();
    savePersistentSettings();
}

void MainWindow::loadPersistentSettings()
{
    const ClientSettingsSnapshot snapshot = settings_.load();

    if (baseUrlEdit_) {
        baseUrlEdit_->setText(snapshot.baseUrl);
    }
    if (playerIdEdit_) {
        playerIdEdit_->setText(snapshot.playerId);
    }
    if (memoryTypeCombo_) {
        const int memoryTypeIndex = memoryTypeCombo_->findText(snapshot.memoryTypeFilter);
        if (memoryTypeIndex >= 0) {
            memoryTypeCombo_->setCurrentIndex(memoryTypeIndex);
        }
    }
    if (memorySearchEdit_) {
        memorySearchEdit_->setText(snapshot.memorySearchText);
    }

    pendingSelectedNpcId_ = snapshot.selectedNpcId;
}

void MainWindow::savePersistentSettings() const
{
    ClientSettingsSnapshot snapshot;
    snapshot.baseUrl = baseUrlEdit_ ? baseUrlEdit_->text() : QString();
    snapshot.playerId = playerIdEdit_ ? playerIdEdit_->text() : QString();
    snapshot.selectedNpcId = npcCombo_ ? npcCombo_->currentData().toString() : QString();
    snapshot.rightTabIndex = 0;
    snapshot.memoryTypeFilter = memoryTypeCombo_ ? memoryTypeCombo_->currentText() : QString();
    snapshot.memorySearchText = memorySearchEdit_ ? memorySearchEdit_->text() : QString();

    settings_.save(snapshot);
}
