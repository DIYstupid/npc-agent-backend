#include "SseEventParser.h"

namespace {
QByteArray stripTrailingCarriageReturn(QByteArray line)
{
    if (line.endsWith('\r')) {
        line.chop(1);
    }

    return line;
}

QByteArray stripSingleLeadingSpace(QByteArray value)
{
    if (value.startsWith(' ')) {
        value.remove(0, 1);
    }

    return value;
}
}

QList<SseEvent> SseEventParser::append(const QByteArray &chunk)
{
    buffer_.append(chunk);

    QList<SseEvent> events;
    while (true) {
        int delimiterLength = 0;
        const int delimiterIndex = nextDelimiterIndex(&delimiterLength);
        if (delimiterIndex < 0) {
            break;
        }

        const QByteArray frame = buffer_.left(delimiterIndex);
        buffer_.remove(0, delimiterIndex + delimiterLength);

        const SseEvent event = parseEvent(frame);
        if (!event.event.isEmpty() || !event.data.isEmpty()) {
            events.append(event);
        }
    }

    return events;
}

QList<SseEvent> SseEventParser::finish()
{
    if (buffer_.trimmed().isEmpty()) {
        buffer_.clear();
        return {};
    }

    const SseEvent event = parseEvent(buffer_);
    buffer_.clear();

    if (event.event.isEmpty() && event.data.isEmpty()) {
        return {};
    }

    return {event};
}

void SseEventParser::clear()
{
    buffer_.clear();
}

int SseEventParser::nextDelimiterIndex(int *delimiterLength) const
{
    const int lfIndex = buffer_.indexOf("\n\n");
    const int crlfIndex = buffer_.indexOf("\r\n\r\n");

    if (lfIndex < 0 && crlfIndex < 0) {
        return -1;
    }

    if (crlfIndex >= 0 && (lfIndex < 0 || crlfIndex < lfIndex)) {
        if (delimiterLength) {
            *delimiterLength = 4;
        }
        return crlfIndex;
    }

    if (delimiterLength) {
        *delimiterLength = 2;
    }
    return lfIndex;
}

SseEvent SseEventParser::parseEvent(const QByteArray &frame)
{
    SseEvent event;
    event.event = "message";

    QList<QByteArray> dataLines;
    const QList<QByteArray> lines = frame.split('\n');
    for (QByteArray line : lines) {
        line = stripTrailingCarriageReturn(line);
        if (line.isEmpty() || line.startsWith(':')) {
            continue;
        }

        const int colonIndex = line.indexOf(':');
        const QByteArray field = colonIndex < 0 ? line : line.left(colonIndex);
        const QByteArray value = colonIndex < 0
            ? QByteArray()
            : stripSingleLeadingSpace(line.mid(colonIndex + 1));

        if (field == "event") {
            event.event = QString::fromUtf8(value).trimmed();
        } else if (field == "data") {
            dataLines.append(value);
        }
    }

    QByteArray data;
    for (int index = 0; index < dataLines.size(); ++index) {
        if (index > 0) {
            data.append('\n');
        }
        data.append(dataLines.at(index));
    }

    event.data = QString::fromUtf8(data);
    return event;
}
