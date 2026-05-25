#include "ui/AsyncRequestTracker.h"

#include <QSignalSpy>
#include <QtTest/QtTest>

class AsyncRequestTrackerTests : public QObject
{
    Q_OBJECT

private slots:
    void tracksConcurrentOperations();
    void ignoresUnexpectedFinish();
};

void AsyncRequestTrackerTests::tracksConcurrentOperations()
{
    AsyncRequestTracker tracker;
    QSignalSpy busySpy(&tracker, &AsyncRequestTracker::busyChanged);
    QSignalSpy stateSpy(&tracker, &AsyncRequestTracker::stateChanged);

    QCOMPARE(tracker.statusText(), QString("Idle"));

    tracker.begin("chat");
    QVERIFY(tracker.isBusy());
    QVERIFY(tracker.isBusy("chat"));
    QCOMPARE(tracker.statusText(), QString("Loading: chat"));
    QCOMPARE(busySpy.count(), 1);

    tracker.begin("chat");
    QCOMPARE(tracker.statusText(), QString("Loading: chat x2"));

    tracker.begin("health");
    QVERIFY(tracker.statusText().contains("chat x2"));
    QVERIFY(tracker.statusText().contains("health"));

    tracker.finish("chat", true, 200);
    QVERIFY(tracker.isBusy("chat"));
    QVERIFY(tracker.isBusy("health"));

    tracker.finish("chat", true, 200);
    QVERIFY(!tracker.isBusy("chat"));
    QVERIFY(tracker.isBusy("health"));

    tracker.finish("health", true, 200);
    QVERIFY(!tracker.isBusy());
    QCOMPARE(tracker.statusText(), QString("Idle - health ok"));
    QCOMPARE(busySpy.count(), 2);
    QVERIFY(stateSpy.count() >= 5);
}

void AsyncRequestTrackerTests::ignoresUnexpectedFinish()
{
    AsyncRequestTracker tracker;
    QSignalSpy busySpy(&tracker, &AsyncRequestTracker::busyChanged);
    QSignalSpy stateSpy(&tracker, &AsyncRequestTracker::stateChanged);

    tracker.finish("missing", false, 500);

    QVERIFY(!tracker.isBusy());
    QCOMPARE(tracker.statusText(), QString("Idle"));
    QCOMPARE(busySpy.count(), 0);
    QCOMPARE(stateSpy.count(), 0);
}

QTEST_MAIN(AsyncRequestTrackerTests)

#include "TestAsyncRequestTracker.moc"
