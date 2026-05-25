#pragma once

#include <functional>

#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QObject>
#include <QString>
#include <QStringList>
#include <QUrl>
#include <QUrlQuery>

#include "api/SseEventParser.h"

class QNetworkReply;
class QTimer;

class ApiClient : public QObject
{
    Q_OBJECT

public:
    explicit ApiClient(QObject *parent = nullptr);

    QUrl baseUrl() const;
    void setBaseUrl(const QUrl &baseUrl);
    void setDefaultTimeoutMs(int timeoutMs);
    void setOperationTimeoutMs(const QString &operation, int timeoutMs);

    void fetchHealth();
    void fetchNpcs();
    void fetchGameState(const QString &playerId);
    void fetchChatHistory(const QString &playerId, const QString &npcId);
    void clearChatHistory(const QString &playerId, const QString &npcId);
    void sendChat(const QString &npcId, const QString &playerId, const QString &message);
    void sendChatStream(const QString &npcId, const QString &playerId, const QString &message);
    void fetchDebugPrompt(const QString &npcId, const QString &playerId, const QString &message);
    void fetchLongTermMemories(
        const QString &npcId,
        const QString &playerId,
        const QString &memoryType = QString());
    void searchLongTermMemories(
        const QString &npcId,
        const QString &playerId,
        const QString &query,
        const QString &memoryType = QString());
    void createLongTermMemory(
        const QString &npcId,
        const QString &playerId,
        const QString &text,
        const QString &memoryType,
        int importance,
        const QStringList &tags);
    void updateLongTermMemory(
        const QString &memoryId,
        const QString &text,
        const QString &memoryType,
        int importance,
        const QStringList &tags);
    void deleteLongTermMemory(const QString &memoryId);
    void fetchSummary(const QString &playerId, const QString &npcId);
    void fetchQuests(const QString &playerId);
    void applyWorldInteraction(const QJsonObject &payload);
    void applyWorldAction(const QJsonObject &payload);
    void fetchWorldEvents(const QString &playerId, int limit = 50);
    void fetchTraces(int limit = 20);
    void fetchLatestTrace();
    void fetchTrace(const QString &requestId);
    void cancelOperation(const QString &operation);
    void cancelAllRequests();

signals:
    void requestStarted(const QString &operation);
    void requestFinished(const QString &operation, bool success, int statusCode);
    void requestCancelled(const QString &operation);
    void requestTimedOut(const QString &operation, int timeoutMs);

    void healthLoaded(const QJsonObject &health);
    void npcsLoaded(const QJsonArray &npcs);
    void gameStateLoaded(const QJsonObject &state);
    void chatHistoryLoaded(const QJsonObject &history);
    void chatLoaded(const QJsonObject &chatResponse);
    void chatStreamStarted(const QJsonObject &payload);
    void chatStreamDelta(const QString &text);
    void debugPromptLoaded(const QJsonObject &debugPrompt);
    void longTermMemoriesLoaded(const QJsonObject &payload);
    void longTermSearchLoaded(const QJsonArray &memories);
    void longTermMemorySaved(const QJsonObject &memory);
    void longTermMemoryDeleted(const QString &memoryId);
    void summaryLoaded(const QJsonObject &summary);
    void questsLoaded(const QJsonObject &quests);
    void worldInteractionApplied(const QJsonObject &response);
    void worldActionApplied(const QJsonObject &response);
    void worldEventsLoaded(const QJsonArray &events);
    void tracesLoaded(const QJsonArray &traces);
    void traceLoaded(const QJsonObject &trace);
    void apiError(const QString &operation, const QString &message, int statusCode);

private:
    using JsonHandler = std::function<void(const QJsonDocument &)>;
    struct ReplyContext
    {
        QString operation;
        QTimer *timer = nullptr;
        int timeoutMs = 0;
        bool cancelled = false;
        bool timedOut = false;
        bool streaming = false;
        bool sseFinalReceived = false;
        bool sseErrorReceived = false;
        SseEventParser sseParser;
    };

    QUrl buildUrl(const QString &path, const QUrlQuery &query = QUrlQuery()) const;
    int timeoutMsForOperation(const QString &operation) const;
    void trackReply(QNetworkReply *reply, const QString &operation);
    void getJson(const QString &operation, const QString &path, const QUrlQuery &query, JsonHandler handler);
    void postJson(const QString &operation, const QString &path, const QJsonObject &payload, JsonHandler handler);
    void postSse(const QString &operation, const QString &path, const QJsonObject &payload);
    void patchJson(const QString &operation, const QString &path, const QJsonObject &payload, JsonHandler handler);
    void deleteJson(const QString &operation, const QString &path, JsonHandler handler);
    void handleReply(QNetworkReply *reply, const QString &operation, JsonHandler handler);
    void handleSseReadyRead(QNetworkReply *reply);
    void handleSseFinished(QNetworkReply *reply, const QString &operation);
    void processSseEvent(QNetworkReply *reply, const SseEvent &event);

    QUrl baseUrl_;
    QNetworkAccessManager network_;
    QHash<QNetworkReply *, ReplyContext> activeReplies_;
    QHash<QString, int> operationTimeouts_;
    int defaultTimeoutMs_ = 15000;
};
