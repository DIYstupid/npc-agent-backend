#include "ClientCache.h"

#include <QDateTime>
#include <QList>

ClientCache::ClientCache(int defaultTtlMs)
    : defaultTtlMs_(defaultTtlMs)
{
}

bool ClientCache::get(const QString &key, QJsonValue *value) const
{
    const auto it = entries_.constFind(key);
    if (it == entries_.constEnd()) {
        return false;
    }

    const qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (it->ttlMs > 0 && now - it->storedAtMs > it->ttlMs) {
        return false;
    }

    if (value) {
        *value = it->value;
    }
    return true;
}

void ClientCache::put(const QString &key, const QJsonValue &value, int ttlMs)
{
    Entry entry;
    entry.value = value;
    entry.storedAtMs = QDateTime::currentMSecsSinceEpoch();
    entry.ttlMs = ttlMs < 0 ? defaultTtlMs_ : ttlMs;
    entries_.insert(key, entry);
}

void ClientCache::invalidate(const QString &key)
{
    entries_.remove(key);
}

void ClientCache::invalidatePrefix(const QString &prefix)
{
    const QList<QString> keys = entries_.keys();
    for (const QString &key : keys) {
        if (key.startsWith(prefix)) {
            entries_.remove(key);
        }
    }
}

void ClientCache::clear()
{
    entries_.clear();
}
