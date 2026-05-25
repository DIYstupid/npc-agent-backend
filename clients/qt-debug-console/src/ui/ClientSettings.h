#pragma once

#include <QByteArray>
#include <QList>
#include <QString>

struct ClientSettingsSnapshot
{
    QString baseUrl;
    QString playerId;
    QString selectedNpcId;
    int rightTabIndex = 0;
    QList<int> mainSplitterSizes;
    QByteArray windowGeometry;
    QByteArray windowState;
    QString memoryTypeFilter;
    QString memorySearchText;
};

class ClientSettings
{
public:
    ClientSettings();
    explicit ClientSettings(const QString &settingsFilePath);

    static QString defaultBaseUrl();
    static QString defaultPlayerId();

    ClientSettingsSnapshot load() const;
    void save(const ClientSettingsSnapshot &snapshot) const;
    void clear() const;

private:
    QString settingsFilePath_;
};
