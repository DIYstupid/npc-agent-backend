#pragma once

#include <QByteArray>
#include <QList>
#include <QString>

struct SseEvent
{
    QString event;
    QString data;
};

class SseEventParser
{
public:
    QList<SseEvent> append(const QByteArray &chunk);
    QList<SseEvent> finish();
    void clear();

private:
    int nextDelimiterIndex(int *delimiterLength) const;
    static SseEvent parseEvent(const QByteArray &frame);

    QByteArray buffer_;
};
