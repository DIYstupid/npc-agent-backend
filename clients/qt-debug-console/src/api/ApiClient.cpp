#include "ApiClient.h"

#include <QJsonParseError>
#include <QList>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTimer>

namespace {
constexpr auto JsonContentType = "application/json";
constexpr auto TextEventStreamContentType = "text/event-stream";
}

ApiClient::ApiClient(QObject *parent)
    : QObject(parent),
      baseUrl_("http://127.0.0.1:8000")
{
    operationTimeouts_.insert("chat", 90000);
    operationTimeouts_.insert("debug_prompt", 60000);
    operationTimeouts_.insert("world_interaction", 60000);
    operationTimeouts_.insert("world_action", 60000);
}

QUrl ApiClient::baseUrl() const
{
    return baseUrl_;
}

void ApiClient::setBaseUrl(const QUrl &baseUrl)
{
    baseUrl_ = baseUrl;
}

void ApiClient::setDefaultTimeoutMs(int timeoutMs)
{
    defaultTimeoutMs_ = timeoutMs;
}

void ApiClient::setOperationTimeoutMs(const QString &operation, int timeoutMs)
{
    operationTimeouts_.insert(operation, timeoutMs);
}

void ApiClient::fetchHealth()
{
    getJson("health", "/health", QUrlQuery(), [this](const QJsonDocument &document) {
        emit healthLoaded(document.object());
    });
}

void ApiClient::fetchNpcs()
{
    getJson("list_npcs", "/npcs", QUrlQuery(), [this](const QJsonDocument &document) {
        emit npcsLoaded(document.array());
    });
}

void ApiClient::fetchGameState(const QString &playerId)
{
    getJson("game_state", QString("/game/state/%1").arg(playerId), QUrlQuery(), [this](const QJsonDocument &document) {
        emit gameStateLoaded(document.object());
    });
}

void ApiClient::fetchChatHistory(const QString &playerId, const QString &npcId)
{
    getJson(
        "chat_history",
        QString("/chat/history/%1/%2").arg(playerId, npcId),
        QUrlQuery(),
        [this](const QJsonDocument &document) {
            emit chatHistoryLoaded(document.object());
        });
}

void ApiClient::clearChatHistory(const QString &playerId, const QString &npcId)
{
    deleteJson(
        "clear_chat_history",
        QString("/chat/history/%1/%2").arg(playerId, npcId),
        [this](const QJsonDocument &) {
            emit chatHistoryLoaded(QJsonObject{{"messages", QJsonArray()}});
        });
}

void ApiClient::sendChat(const QString &npcId, const QString &playerId, const QString &message)
{
    const QJsonObject payload{
        {"player_id", playerId},
        {"message", message},
    };

    postJson("chat", QString("/chat/%1").arg(npcId), payload, [this](const QJsonDocument &document) {
        emit chatLoaded(document.object());
    });
}

void ApiClient::sendChatStream(const QString &npcId, const QString &playerId, const QString &message)
{
    const QJsonObject payload{
        {"player_id", playerId},
        {"message", message},
    };

    postSse("chat", QString("/chat/%1/stream").arg(npcId), payload);
}

void ApiClient::fetchDebugPrompt(const QString &npcId, const QString &playerId, const QString &message)
{
    const QJsonObject payload{
        {"player_id", playerId},
        {"message", message},
    };

    postJson(
        "debug_prompt",
        QString("/chat/%1/debug-prompt").arg(npcId),
        payload,
        [this](const QJsonDocument &document) {
            emit debugPromptLoaded(document.object());
        });
}

void ApiClient::fetchLongTermMemories(const QString &npcId, const QString &playerId, const QString &memoryType)
{
    QUrlQuery query;
    query.addQueryItem("npc_id", npcId);
    query.addQueryItem("player_id", playerId);
    if (!memoryType.trimmed().isEmpty()) {
        query.addQueryItem("memory_type", memoryType.trimmed());
    }

    getJson("long_term_memory_list", "/memory/long-term", query, [this](const QJsonDocument &document) {
        emit longTermMemoriesLoaded(document.object());
    });
}

void ApiClient::searchLongTermMemories(
    const QString &npcId,
    const QString &playerId,
    const QString &queryText,
    const QString &memoryType)
{
    QUrlQuery query;
    query.addQueryItem("npc_id", npcId);
    query.addQueryItem("player_id", playerId);
    query.addQueryItem("query", queryText);
    if (!memoryType.trimmed().isEmpty()) {
        query.addQueryItem("memory_type", memoryType.trimmed());
    }

    getJson("long_term_memory_search", "/memory/long-term/search", query, [this](const QJsonDocument &document) {
        emit longTermSearchLoaded(document.array());
    });
}

void ApiClient::createLongTermMemory(
    const QString &npcId,
    const QString &playerId,
    const QString &text,
    const QString &memoryType,
    int importance,
    const QStringList &tags)
{
    QJsonArray tagArray;
    for (const QString &tag : tags) {
        if (!tag.trimmed().isEmpty()) {
            tagArray.append(tag.trimmed());
        }
    }

    const QJsonObject payload{
        {"npc_id", npcId},
        {"player_id", playerId},
        {"text", text},
        {"memory_type", memoryType.trimmed().isEmpty() ? QString("general") : memoryType.trimmed()},
        {"importance", importance},
        {"tags", tagArray},
    };

    postJson("create_long_term_memory", "/memory/long-term", payload, [this](const QJsonDocument &document) {
        emit longTermMemorySaved(document.object());
    });
}

void ApiClient::updateLongTermMemory(
    const QString &memoryId,
    const QString &text,
    const QString &memoryType,
    int importance,
    const QStringList &tags)
{
    QJsonArray tagArray;
    for (const QString &tag : tags) {
        if (!tag.trimmed().isEmpty()) {
            tagArray.append(tag.trimmed());
        }
    }

    const QJsonObject payload{
        {"text", text},
        {"memory_type", memoryType.trimmed().isEmpty() ? QString("general") : memoryType.trimmed()},
        {"importance", importance},
        {"tags", tagArray},
    };

    patchJson(
        "update_long_term_memory",
        QString("/memory/long-term/%1").arg(memoryId),
        payload,
        [this](const QJsonDocument &document) {
            emit longTermMemorySaved(document.object());
        });
}

void ApiClient::deleteLongTermMemory(const QString &memoryId)
{
    deleteJson(
        "delete_long_term_memory",
        QString("/memory/long-term/%1").arg(memoryId),
        [this, memoryId](const QJsonDocument &) {
            emit longTermMemoryDeleted(memoryId);
        });
}

void ApiClient::fetchSummary(const QString &playerId, const QString &npcId)
{
    getJson(
        "summary_memory",
        QString("/memory/summary/%1/%2").arg(playerId, npcId),
        QUrlQuery(),
        [this](const QJsonDocument &document) {
            emit summaryLoaded(document.object());
        });
}

void ApiClient::fetchQuests(const QString &playerId)
{
    getJson("quest_state", QString("/quest/%1").arg(playerId), QUrlQuery(), [this](const QJsonDocument &document) {
        emit questsLoaded(document.object());
    });
}

void ApiClient::applyWorldInteraction(const QJsonObject &payload)
{
    postJson("world_interaction", "/world/interactions", payload, [this](const QJsonDocument &document) {
        emit worldInteractionApplied(document.object());
    });
}

void ApiClient::applyWorldAction(const QJsonObject &payload)
{
    postJson("world_action", "/world/actions", payload, [this](const QJsonDocument &document) {
        emit worldActionApplied(document.object());
    });
}

void ApiClient::fetchWorldEvents(const QString &playerId, int limit)
{
    QUrlQuery query;
    if (!playerId.trimmed().isEmpty()) {
        query.addQueryItem("player_id", playerId.trimmed());
    }
    query.addQueryItem("limit", QString::number(limit));

    getJson("world_events", "/world/events", query, [this](const QJsonDocument &document) {
        emit worldEventsLoaded(document.object().value("events").toArray());
    });
}

void ApiClient::fetchTraces(int limit)
{
    QUrlQuery query;
    query.addQueryItem("limit", QString::number(limit));

    getJson("trace_list", "/debug/traces", query, [this](const QJsonDocument &document) {
        emit tracesLoaded(document.object().value("traces").toArray());
    });
}

void ApiClient::fetchLatestTrace()
{
    getJson("latest_trace", "/debug/traces/latest", QUrlQuery(), [this](const QJsonDocument &document) {
        emit traceLoaded(document.object());
    });
}

void ApiClient::fetchTrace(const QString &requestId)
{
    getJson("trace_detail", QString("/debug/traces/%1").arg(requestId), QUrlQuery(), [this](const QJsonDocument &document) {
        emit traceLoaded(document.object());
    });
}

void ApiClient::cancelOperation(const QString &operation)
{
    QList<QNetworkReply *> replies;
    for (auto it = activeReplies_.begin(); it != activeReplies_.end(); ++it) {
        if (it.value().operation == operation) {
            replies.append(it.key());
        }
    }

    for (QNetworkReply *reply : replies) {
        auto it = activeReplies_.find(reply);
        if (it == activeReplies_.end()) {
            continue;
        }

        it.value().cancelled = true;
        reply->abort();
    }
}

void ApiClient::cancelAllRequests()
{
    const QList<QNetworkReply *> replies = activeReplies_.keys();
    for (QNetworkReply *reply : replies) {
        auto it = activeReplies_.find(reply);
        if (it == activeReplies_.end()) {
            continue;
        }

        it.value().cancelled = true;
        reply->abort();
    }
}

QUrl ApiClient::buildUrl(const QString &path, const QUrlQuery &query) const
{
    QUrl url = baseUrl_;
    QString urlPath = url.path();
    if (urlPath.endsWith('/')) {
        urlPath.chop(1);
    }

    url.setPath(urlPath + path);
    url.setQuery(query);
    return url;
}

int ApiClient::timeoutMsForOperation(const QString &operation) const
{
    return operationTimeouts_.value(operation, defaultTimeoutMs_);
}

void ApiClient::trackReply(QNetworkReply *reply, const QString &operation)
{
    ReplyContext context;
    context.operation = operation;
    context.timeoutMs = timeoutMsForOperation(operation);

    if (context.timeoutMs > 0) {
        auto *timer = new QTimer(this);
        timer->setSingleShot(true);
        context.timer = timer;

        connect(timer, &QTimer::timeout, this, [this, reply]() {
            auto it = activeReplies_.find(reply);
            if (it == activeReplies_.end()) {
                return;
            }

            it.value().timedOut = true;
            reply->abort();
        });
        timer->start(context.timeoutMs);
    }

    activeReplies_.insert(reply, context);
}

void ApiClient::getJson(const QString &operation, const QString &path, const QUrlQuery &query, JsonHandler handler)
{
    QNetworkRequest request(buildUrl(path, query));
    request.setHeader(QNetworkRequest::ContentTypeHeader, JsonContentType);

    emit requestStarted(operation);
    QNetworkReply *reply = network_.get(request);
    trackReply(reply, operation);
    connect(reply, &QNetworkReply::finished, this, [this, reply, operation, handler]() {
        handleReply(reply, operation, handler);
    });
}

void ApiClient::postJson(const QString &operation, const QString &path, const QJsonObject &payload, JsonHandler handler)
{
    QNetworkRequest request(buildUrl(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, JsonContentType);

    const QByteArray body = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    emit requestStarted(operation);
    QNetworkReply *reply = network_.post(request, body);
    trackReply(reply, operation);
    connect(reply, &QNetworkReply::finished, this, [this, reply, operation, handler]() {
        handleReply(reply, operation, handler);
    });
}

void ApiClient::postSse(const QString &operation, const QString &path, const QJsonObject &payload)
{
    QNetworkRequest request(buildUrl(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, JsonContentType);
    request.setRawHeader("Accept", TextEventStreamContentType);

    const QByteArray body = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    emit requestStarted(operation);
    QNetworkReply *reply = network_.post(request, body);
    trackReply(reply, operation);

    auto it = activeReplies_.find(reply);
    if (it != activeReplies_.end()) {
        it.value().streaming = true;
    }

    connect(reply, &QNetworkReply::readyRead, this, [this, reply]() {
        handleSseReadyRead(reply);
    });
    connect(reply, &QNetworkReply::finished, this, [this, reply, operation]() {
        handleSseFinished(reply, operation);
    });
}

void ApiClient::patchJson(const QString &operation, const QString &path, const QJsonObject &payload, JsonHandler handler)
{
    QNetworkRequest request(buildUrl(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, JsonContentType);

    const QByteArray body = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    emit requestStarted(operation);
    QNetworkReply *reply = network_.sendCustomRequest(request, "PATCH", body);
    trackReply(reply, operation);
    connect(reply, &QNetworkReply::finished, this, [this, reply, operation, handler]() {
        handleReply(reply, operation, handler);
    });
}

void ApiClient::deleteJson(const QString &operation, const QString &path, JsonHandler handler)
{
    QNetworkRequest request(buildUrl(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, JsonContentType);

    emit requestStarted(operation);
    QNetworkReply *reply = network_.deleteResource(request);
    trackReply(reply, operation);
    connect(reply, &QNetworkReply::finished, this, [this, reply, operation, handler]() {
        handleReply(reply, operation, handler);
    });
}

void ApiClient::handleSseReadyRead(QNetworkReply *reply)
{
    auto it = activeReplies_.find(reply);
    if (it == activeReplies_.end()) {
        return;
    }

    const QList<SseEvent> events = it.value().sseParser.append(reply->readAll());
    for (const SseEvent &event : events) {
        processSseEvent(reply, event);
    }
}

void ApiClient::handleSseFinished(QNetworkReply *reply, const QString &operation)
{
    auto it = activeReplies_.find(reply);
    if (it == activeReplies_.end()) {
        reply->deleteLater();
        return;
    }

    if (reply->bytesAvailable() > 0) {
        const QList<SseEvent> events = it.value().sseParser.append(reply->readAll());
        for (const SseEvent &event : events) {
            processSseEvent(reply, event);
        }
    }

    const QList<SseEvent> remainingEvents = it.value().sseParser.finish();
    for (const SseEvent &event : remainingEvents) {
        processSseEvent(reply, event);
    }

    ReplyContext context = activeReplies_.take(reply);
    if (context.timer) {
        context.timer->stop();
        context.timer->deleteLater();
    }

    const int statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    const auto networkError = reply->error();
    const QString errorString = reply->errorString();
    reply->deleteLater();

    if (context.cancelled) {
        emit requestCancelled(operation);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    if (context.timedOut) {
        const QString message = QString("Request timed out after %1 ms").arg(context.timeoutMs);
        emit requestTimedOut(operation, context.timeoutMs);
        emit apiError(operation, message, statusCode);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    if (networkError != QNetworkReply::NoError || statusCode >= 400) {
        emit apiError(operation, errorString, statusCode);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    if (context.sseErrorReceived) {
        emit requestFinished(operation, false, statusCode);
        return;
    }

    if (!context.sseFinalReceived) {
        emit apiError(operation, "Stream ended before final event", statusCode);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    emit requestFinished(operation, true, statusCode);
}

void ApiClient::processSseEvent(QNetworkReply *reply, const SseEvent &event)
{
    auto it = activeReplies_.find(reply);
    if (it == activeReplies_.end()) {
        return;
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(event.data.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        it.value().sseErrorReceived = true;
        emit apiError(
            it.value().operation,
            QString("Invalid SSE %1 payload: %2").arg(event.event, parseError.errorString()),
            0);
        return;
    }

    const QJsonObject payload = document.object();
    if (event.event == "start") {
        emit chatStreamStarted(payload);
    } else if (event.event == "delta") {
        emit chatStreamDelta(payload.value("text").toString());
    } else if (event.event == "final") {
        it.value().sseFinalReceived = true;
        emit chatLoaded(payload);
    } else if (event.event == "error") {
        it.value().sseErrorReceived = true;
        emit apiError(
            it.value().operation,
            payload.value("message").toString("Streaming chat failed"),
            0);
    }
}

void ApiClient::handleReply(QNetworkReply *reply, const QString &operation, JsonHandler handler)
{
    ReplyContext context = activeReplies_.take(reply);
    if (context.timer) {
        context.timer->stop();
        context.timer->deleteLater();
    }

    const int statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    const QByteArray body = reply->readAll();
    const auto networkError = reply->error();
    const QString errorString = reply->errorString();
    reply->deleteLater();

    if (context.cancelled) {
        emit requestCancelled(operation);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    if (context.timedOut) {
        const QString message = QString("Request timed out after %1 ms").arg(context.timeoutMs);
        emit requestTimedOut(operation, context.timeoutMs);
        emit apiError(operation, message, statusCode);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    if (networkError != QNetworkReply::NoError || statusCode >= 400) {
        const QString message = body.isEmpty()
            ? errorString
            : QString::fromUtf8(body);
        emit apiError(operation, message, statusCode);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(body, &parseError);
    if (parseError.error != QJsonParseError::NoError) {
        emit apiError(operation, parseError.errorString(), statusCode);
        emit requestFinished(operation, false, statusCode);
        return;
    }

    handler(document);
    emit requestFinished(operation, true, statusCode);
}
