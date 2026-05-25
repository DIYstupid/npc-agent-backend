#pragma once

#include <QHash>
#include <QJsonValue>
#include <QString>
#include <QtGlobal>

class ClientCache
{
public:
    explicit ClientCache(int defaultTtlMs = 30000);

    bool get(const QString &key, QJsonValue *value) const;
    void put(const QString &key, const QJsonValue &value, int ttlMs = -1);
    void invalidate(const QString &key);
    void invalidatePrefix(const QString &prefix);
    void clear();

private:
    struct Entry
    {
        QJsonValue value;
        qint64 storedAtMs = 0;
        int ttlMs = 0;
    };

    int defaultTtlMs_ = 30000;
    QHash<QString, Entry> entries_;
};
