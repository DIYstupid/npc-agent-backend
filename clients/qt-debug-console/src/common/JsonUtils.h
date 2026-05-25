#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QString>
#include <QStringList>

QString formatJson(const QJsonValue &value);
QString formatJsonObject(const QJsonObject &object);
QString formatJsonArray(const QJsonArray &array);
QString jsonValueToDisplayString(const QJsonValue &value);
QStringList jsonArrayToStringList(const QJsonArray &array);
