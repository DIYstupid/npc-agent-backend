#include "JsonUtils.h"

#include <QJsonDocument>

QString formatJson(const QJsonValue &value)
{
    if (value.isObject()) {
        return formatJsonObject(value.toObject());
    }

    if (value.isArray()) {
        return formatJsonArray(value.toArray());
    }

    return jsonValueToDisplayString(value);
}

QString formatJsonObject(const QJsonObject &object)
{
    const QJsonDocument document(object);
    return QString::fromUtf8(document.toJson(QJsonDocument::Indented));
}

QString formatJsonArray(const QJsonArray &array)
{
    const QJsonDocument document(array);
    return QString::fromUtf8(document.toJson(QJsonDocument::Indented));
}

QString jsonValueToDisplayString(const QJsonValue &value)
{
    if (value.isString()) {
        return value.toString();
    }

    if (value.isDouble()) {
        return QString::number(value.toDouble());
    }

    if (value.isBool()) {
        return value.toBool() ? "true" : "false";
    }

    if (value.isNull() || value.isUndefined()) {
        return "";
    }

    return formatJson(value);
}

QStringList jsonArrayToStringList(const QJsonArray &array)
{
    QStringList values;
    values.reserve(array.size());

    for (const QJsonValue &value : array) {
        values.append(jsonValueToDisplayString(value));
    }

    return values;
}
