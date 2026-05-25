#include "api/SseEventParser.h"

#include <QtTest/QtTest>

class SseEventParserTests : public QObject
{
    Q_OBJECT

private slots:
    void parsesChunkedEvents();
    void parsesCrLfAndMultiLineData();
    void flushesFinalFrameWithoutDelimiter();
};

void SseEventParserTests::parsesChunkedEvents()
{
    SseEventParser parser;

    QList<SseEvent> events = parser.append("event: del");
    QVERIFY(events.isEmpty());

    events = parser.append("ta\ndata: {\"text\":\"h\"}\n\n");
    QCOMPARE(events.size(), 1);
    QCOMPARE(events.at(0).event, QString("delta"));
    QCOMPARE(events.at(0).data, QString("{\"text\":\"h\"}"));

    events = parser.append("event: final\ndata: {\"reply\":\"hi\"}\n\n");
    QCOMPARE(events.size(), 1);
    QCOMPARE(events.at(0).event, QString("final"));
    QCOMPARE(events.at(0).data, QString("{\"reply\":\"hi\"}"));
}

void SseEventParserTests::parsesCrLfAndMultiLineData()
{
    SseEventParser parser;

    const QList<SseEvent> events = parser.append(
        "event: message\r\n"
        "data: first\r\n"
        "data: second\r\n"
        "\r\n");

    QCOMPARE(events.size(), 1);
    QCOMPARE(events.at(0).event, QString("message"));
    QCOMPARE(events.at(0).data, QString("first\nsecond"));
}

void SseEventParserTests::flushesFinalFrameWithoutDelimiter()
{
    SseEventParser parser;
    QVERIFY(parser.append("event: error\ndata: {\"message\":\"failed\"}").isEmpty());

    const QList<SseEvent> events = parser.finish();
    QCOMPARE(events.size(), 1);
    QCOMPARE(events.at(0).event, QString("error"));
    QCOMPARE(events.at(0).data, QString("{\"message\":\"failed\"}"));
}

QTEST_MAIN(SseEventParserTests)

#include "TestSseEventParser.moc"
