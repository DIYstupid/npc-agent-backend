#include "ui/ClientCache.h"

#include <QJsonObject>
#include <QJsonValue>
#include <QtTest/QtTest>

class ClientCacheTests : public QObject
{
    Q_OBJECT

private slots:
    void returnsStoredValue();
    void expiresStoredValueAfterTtl();
    void invalidatesSingleKeyAndPrefix();
};

void ClientCacheTests::returnsStoredValue()
{
    ClientCache cache(1000);
    cache.put("npc", QJsonValue(QJsonObject{{"name", "Lyra"}}));

    QJsonValue value;
    QVERIFY(cache.get("npc", &value));
    QCOMPARE(value.toObject().value("name").toString(), QString("Lyra"));
}

void ClientCacheTests::expiresStoredValueAfterTtl()
{
    ClientCache cache(5);
    cache.put("short", QJsonValue(QString("cached")));

    QTest::qWait(30);

    QVERIFY(!cache.get("short", nullptr));
}

void ClientCacheTests::invalidatesSingleKeyAndPrefix()
{
    ClientCache cache(1000);
    cache.put("memory::list::npc_a", QJsonValue(1));
    cache.put("memory::search::npc_a", QJsonValue(2));
    cache.put("trace::list", QJsonValue(3));

    cache.invalidate("trace::list");
    QVERIFY(!cache.get("trace::list", nullptr));

    cache.invalidatePrefix("memory::");
    QVERIFY(!cache.get("memory::list::npc_a", nullptr));
    QVERIFY(!cache.get("memory::search::npc_a", nullptr));
}

QTEST_MAIN(ClientCacheTests)

#include "TestClientCache.moc"
