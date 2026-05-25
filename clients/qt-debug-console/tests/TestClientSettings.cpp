#include "ui/ClientSettings.h"

#include <QTemporaryDir>
#include <QtTest/QtTest>

class ClientSettingsTests : public QObject
{
    Q_OBJECT

private slots:
    void loadsDefaultsFromEmptyStore();
    void roundTripsConnectionAndLayout();
    void normalizesBlankConnectionFieldsOnSave();
};

void ClientSettingsTests::loadsDefaultsFromEmptyStore()
{
    QTemporaryDir tempDir;
    QVERIFY(tempDir.isValid());

    const ClientSettings settings(tempDir.filePath("settings.ini"));
    const ClientSettingsSnapshot snapshot = settings.load();

    QCOMPARE(snapshot.baseUrl, ClientSettings::defaultBaseUrl());
    QCOMPARE(snapshot.playerId, ClientSettings::defaultPlayerId());
    QVERIFY(snapshot.selectedNpcId.isEmpty());
    QCOMPARE(snapshot.rightTabIndex, 0);
    QVERIFY(snapshot.mainSplitterSizes.isEmpty());
    QVERIFY(snapshot.windowGeometry.isEmpty());
    QVERIFY(snapshot.windowState.isEmpty());
    QVERIFY(snapshot.memoryTypeFilter.isEmpty());
    QVERIFY(snapshot.memorySearchText.isEmpty());
}

void ClientSettingsTests::roundTripsConnectionAndLayout()
{
    QTemporaryDir tempDir;
    QVERIFY(tempDir.isValid());

    const QString settingsPath = tempDir.filePath("settings.ini");
    const ClientSettings writer(settingsPath);

    ClientSettingsSnapshot saved;
    saved.baseUrl = " http://localhost:9000 ";
    saved.playerId = " player_test ";
    saved.selectedNpcId = " npc_guard ";
    saved.rightTabIndex = 3;
    saved.mainSplitterSizes << 240 << 360 << 480;
    saved.windowGeometry = QByteArray("geometry-bytes");
    saved.windowState = QByteArray("state-bytes");
    saved.memoryTypeFilter = " quest ";
    saved.memorySearchText = " village gate ";
    writer.save(saved);

    const ClientSettings reader(settingsPath);
    const ClientSettingsSnapshot loaded = reader.load();

    QCOMPARE(loaded.baseUrl, QString("http://localhost:9000"));
    QCOMPARE(loaded.playerId, QString("player_test"));
    QCOMPARE(loaded.selectedNpcId, QString("npc_guard"));
    QCOMPARE(loaded.rightTabIndex, 3);
    QCOMPARE(loaded.mainSplitterSizes.size(), 3);
    QCOMPARE(loaded.mainSplitterSizes.at(0), 240);
    QCOMPARE(loaded.mainSplitterSizes.at(1), 360);
    QCOMPARE(loaded.mainSplitterSizes.at(2), 480);
    QCOMPARE(loaded.windowGeometry, QByteArray("geometry-bytes"));
    QCOMPARE(loaded.windowState, QByteArray("state-bytes"));
    QCOMPARE(loaded.memoryTypeFilter, QString("quest"));
    QCOMPARE(loaded.memorySearchText, QString("village gate"));
}

void ClientSettingsTests::normalizesBlankConnectionFieldsOnSave()
{
    QTemporaryDir tempDir;
    QVERIFY(tempDir.isValid());

    const ClientSettings settings(tempDir.filePath("settings.ini"));
    ClientSettingsSnapshot saved;
    saved.baseUrl = "  ";
    saved.playerId = "\t";
    saved.rightTabIndex = -5;
    settings.save(saved);

    const ClientSettingsSnapshot loaded = settings.load();
    QCOMPARE(loaded.baseUrl, ClientSettings::defaultBaseUrl());
    QCOMPARE(loaded.playerId, ClientSettings::defaultPlayerId());
    QCOMPARE(loaded.rightTabIndex, 0);
}

QTEST_MAIN(ClientSettingsTests)

#include "TestClientSettings.moc"
