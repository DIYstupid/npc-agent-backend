#include "ClientSettings.h"

#include <QSettings>
#include <QVariant>
#include <QVariantList>
#include <QtGlobal>

namespace {
constexpr auto OrganizationName = "npc-agent-backend";
constexpr auto ApplicationName = "NPC Agent Debug Console";

constexpr auto BaseUrlKey = "connection/baseUrl";
constexpr auto PlayerIdKey = "connection/playerId";
constexpr auto SelectedNpcIdKey = "connection/selectedNpcId";
constexpr auto RightTabIndexKey = "ui/rightTabIndex";
constexpr auto MainSplitterSizesKey = "ui/mainSplitterSizes";
constexpr auto WindowGeometryKey = "ui/windowGeometry";
constexpr auto WindowStateKey = "ui/windowState";
constexpr auto MemoryTypeFilterKey = "memory/typeFilter";
constexpr auto MemorySearchTextKey = "memory/searchText";

QString normalizedText(const QString &value, const QString &fallback)
{
    const QString trimmed = value.trimmed();
    return trimmed.isEmpty() ? fallback : trimmed;
}

QList<int> intListFromVariant(const QVariant &value)
{
    QList<int> result;
    const QVariantList variants = value.toList();
    result.reserve(variants.size());

    for (const QVariant &item : variants) {
        bool ok = false;
        const int size = item.toInt(&ok);
        if (ok && size >= 0) {
            result.append(size);
        }
    }

    return result;
}

QVariantList variantListFromIntList(const QList<int> &values)
{
    QVariantList result;
    result.reserve(values.size());

    for (int value : values) {
        result.append(value);
    }

    return result;
}

ClientSettingsSnapshot readSettings(QSettings &settings)
{
    ClientSettingsSnapshot snapshot;
    snapshot.baseUrl = normalizedText(settings.value(BaseUrlKey).toString(), ClientSettings::defaultBaseUrl());
    snapshot.playerId = normalizedText(settings.value(PlayerIdKey).toString(), ClientSettings::defaultPlayerId());
    snapshot.selectedNpcId = settings.value(SelectedNpcIdKey).toString().trimmed();
    snapshot.rightTabIndex = qMax(0, settings.value(RightTabIndexKey, 0).toInt());
    snapshot.mainSplitterSizes = intListFromVariant(settings.value(MainSplitterSizesKey));
    snapshot.windowGeometry = settings.value(WindowGeometryKey).toByteArray();
    snapshot.windowState = settings.value(WindowStateKey).toByteArray();
    snapshot.memoryTypeFilter = settings.value(MemoryTypeFilterKey).toString().trimmed();
    snapshot.memorySearchText = settings.value(MemorySearchTextKey).toString().trimmed();
    return snapshot;
}

void writeSettings(QSettings &settings, const ClientSettingsSnapshot &snapshot)
{
    settings.setValue(BaseUrlKey, normalizedText(snapshot.baseUrl, ClientSettings::defaultBaseUrl()));
    settings.setValue(PlayerIdKey, normalizedText(snapshot.playerId, ClientSettings::defaultPlayerId()));
    settings.setValue(SelectedNpcIdKey, snapshot.selectedNpcId.trimmed());
    settings.setValue(RightTabIndexKey, qMax(0, snapshot.rightTabIndex));
    settings.setValue(MainSplitterSizesKey, variantListFromIntList(snapshot.mainSplitterSizes));
    settings.setValue(WindowGeometryKey, snapshot.windowGeometry);
    settings.setValue(WindowStateKey, snapshot.windowState);
    settings.setValue(MemoryTypeFilterKey, snapshot.memoryTypeFilter.trimmed());
    settings.setValue(MemorySearchTextKey, snapshot.memorySearchText.trimmed());
    settings.sync();
}
}

ClientSettings::ClientSettings() = default;

ClientSettings::ClientSettings(const QString &settingsFilePath)
    : settingsFilePath_(settingsFilePath)
{
}

QString ClientSettings::defaultBaseUrl()
{
    return QString("http://127.0.0.1:8000");
}

QString ClientSettings::defaultPlayerId()
{
    return QString("player_001");
}

ClientSettingsSnapshot ClientSettings::load() const
{
    if (settingsFilePath_.isEmpty()) {
        QSettings settings(OrganizationName, ApplicationName);
        return readSettings(settings);
    }

    QSettings settings(settingsFilePath_, QSettings::IniFormat);
    return readSettings(settings);
}

void ClientSettings::save(const ClientSettingsSnapshot &snapshot) const
{
    if (settingsFilePath_.isEmpty()) {
        QSettings settings(OrganizationName, ApplicationName);
        writeSettings(settings, snapshot);
        return;
    }

    QSettings settings(settingsFilePath_, QSettings::IniFormat);
    writeSettings(settings, snapshot);
}

void ClientSettings::clear() const
{
    if (settingsFilePath_.isEmpty()) {
        QSettings settings(OrganizationName, ApplicationName);
        settings.clear();
        settings.sync();
        return;
    }

    QSettings settings(settingsFilePath_, QSettings::IniFormat);
    settings.clear();
    settings.sync();
}
