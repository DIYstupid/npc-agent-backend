#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QMainWindow>

#include "api/ApiClient.h"
#include "ui/AsyncRequestTracker.h"
#include "ui/ClientCache.h"
#include "ui/ClientSettings.h"

class QComboBox;
class QCheckBox;
class QCloseEvent;
class QDockWidget;
class QLabel;
class QLineEdit;
class QListWidget;
class QListWidgetItem;
class QProgressBar;
class QPushButton;
class QSplitter;
class QSpinBox;
class QTableWidget;
class QTextEdit;
class QTimer;
class QTreeWidget;
class QTreeWidgetItem;
class TokenBudgetChart;
class TraceTimelineWidget;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);

protected:
    void closeEvent(QCloseEvent *event) override;

private:
    void setupUi();
    void connectSignals();
    void applyDefaultWindowGeometry();
    void applyDefaultDockLayout();
    void resetLayoutToDefault();
    void loadPersistentSettings();
    void savePersistentSettings() const;
    void applyBaseUrl();
    void refreshAll(bool force = true);
    void refreshNpcScoped(bool force = false);
    void refreshCurrentPanel(bool force = false);
    void sendChat();
    void cancelConversationRequest();
    void cancelAllRequests();
    void requestDebugPrompt();
    void clearHistory();
    void refreshMemory(bool force = true);
    void searchMemory(bool force = true);
    void createMemory();
    void updateMemory();
    void deleteMemory();
    void populateMemoryEditorFromSelection();
    void populateMemoryEditorFromCard(QListWidgetItem *item);
    void requestSelectedTrace();
    void fetchTraceDetail(const QString &requestId, bool force = false);
    void requestNpcs(bool force);
    void requestGameState(bool force);
    void requestChatHistory(bool force);
    void requestSummary(bool force);
    void requestQuests(bool force);
    void requestWorldEvents(bool force);
    void requestLongTermMemories(bool force);
    void requestLongTermMemorySearch(bool force);
    void requestTraces(bool force);
    void executeWorldInteraction();
    void executeWorldAction();
    void updateWorldActionForm();
    void invalidateNpcScopedCache();
    void invalidateMemoryCache();
    void invalidateQuestCache();
    void invalidateWorldEventsCache();
    void invalidateTraceCache();
    QJsonObject buildWorldInteractionPayload() const;
    QJsonObject buildWorldActionPayload() const;
    QString selectedNpcId() const;
    QString playerId() const;
    QString selectedMemoryId() const;
    QStringList memoryTags() const;

    void onNpcsLoaded(const QJsonArray &npcs);
    void onGameStateLoaded(const QJsonObject &state);
    void onChatHistoryLoaded(const QJsonObject &history);
    void onChatLoaded(const QJsonObject &chatResponse);
    void onChatStreamStarted(const QJsonObject &payload);
    void onChatStreamDelta(const QString &text);
    void onDebugPromptLoaded(const QJsonObject &debugPrompt);
    void onLongTermMemoriesLoaded(const QJsonObject &payload);
    void onLongTermSearchLoaded(const QJsonArray &memories);
    void onSummaryLoaded(const QJsonObject &summary);
    void onQuestsLoaded(const QJsonObject &quests);
    void onWorldInteractionApplied(const QJsonObject &response);
    void onWorldActionApplied(const QJsonObject &response);
    void onWorldEventsLoaded(const QJsonArray &events);
    void onTracesLoaded(const QJsonArray &traces);
    void onTraceLoaded(const QJsonObject &trace);
    void onRequestCancelled(const QString &operation);
    void onApiError(const QString &operation, const QString &message, int statusCode);

    void renderNpcTable(const QJsonArray &npcs);
    void renderStateTree(const QJsonObject &state);
    void renderContextReport(const QJsonObject &report);
    void renderActions(const QJsonArray &actions, const QJsonArray &executedActions);
    void renderQuests(const QJsonObject &quests);
    void renderWorldInteractionResult(const QJsonObject &response);
    void renderWorldActionResult(const QJsonObject &response);
    void renderWorldEvents(const QJsonArray &events);
    void renderMemories(const QJsonArray &memories);
    void renderTraces(const QJsonArray &traces);
    void renderTraceDetail(const QJsonObject &trace);
    void renderTraceMemoryHits(const QJsonObject &trace);
    void updateTokenUsage(const QJsonObject &report);
    void selectTraceRow(const QString &requestId);
    QString traceRequestIdAtRow(int row) const;
    void appendChatLine(const QString &speaker, const QString &text);
    void appendStreamingChatDelta(const QString &text);
    void renderNextStreamingChatCharacter();
    void finishStreamingChatRendering();
    void resetStreamingChatState();
    void appendStatus(const QString &line);
    void updateRequestControls();
    void addJsonToTree(QTreeWidgetItem *parent, const QString &key, const QJsonValue &value);

    ApiClient api_;
    AsyncRequestTracker requestTracker_;
    ClientCache cache_;
    ClientSettings settings_;
    QJsonArray npcs_;
    QJsonArray currentMemories_;
    QJsonArray currentTraces_;
    QString pendingMessage_;
    bool pendingMessageRendered_ = false;
    QString streamingReply_;
    QString streamingRenderQueue_;
    bool streamingReplyActive_ = false;
    bool streamingFinalReceived_ = false;
    QString activeTraceRequestId_;
    QString pendingTraceRequestId_;
    QString pendingSelectedNpcId_;
    QString appliedBaseUrlText_;
    bool suppressTraceSelectionFetch_ = false;

    QLineEdit *baseUrlEdit_ = nullptr;
    QLineEdit *playerIdEdit_ = nullptr;
    QComboBox *npcCombo_ = nullptr;
    QSplitter *mainSplitter_ = nullptr;
    QPushButton *refreshButton_ = nullptr;
    QPushButton *healthButton_ = nullptr;
    QPushButton *cancelRequestsButton_ = nullptr;
    QLabel *requestStatusLabel_ = nullptr;
    QDockWidget *contextDock_ = nullptr;
    QDockWidget *actionsDock_ = nullptr;
    QDockWidget *memoryDock_ = nullptr;
    QDockWidget *traceDock_ = nullptr;
    QDockWidget *questDock_ = nullptr;
    QDockWidget *worldActionDock_ = nullptr;
    QDockWidget *worldEventsDock_ = nullptr;
    QDockWidget *statusDock_ = nullptr;

    QTableWidget *npcTable_ = nullptr;
    QTreeWidget *stateTree_ = nullptr;
    QTextEdit *summaryText_ = nullptr;

    QTextEdit *chatView_ = nullptr;
    QLineEdit *messageEdit_ = nullptr;
    QPushButton *sendButton_ = nullptr;
    QPushButton *cancelChatButton_ = nullptr;
    QPushButton *debugPromptButton_ = nullptr;
    QPushButton *clearHistoryButton_ = nullptr;

    QTableWidget *contextTable_ = nullptr;
    TokenBudgetChart *tokenBudgetChart_ = nullptr;
    QProgressBar *tokenUsageBar_ = nullptr;
    QLabel *tokenUsageLabel_ = nullptr;
    QLabel *contextWindowLabel_ = nullptr;
    QTableWidget *sectionTokenTable_ = nullptr;
    QTextEdit *promptText_ = nullptr;
    QTableWidget *actionTable_ = nullptr;
    QTextEdit *rawResponseText_ = nullptr;

    QPushButton *questRefreshButton_ = nullptr;
    QTableWidget *questTable_ = nullptr;
    QTableWidget *questObjectiveTable_ = nullptr;
    QTextEdit *questRawText_ = nullptr;

    QTextEdit *worldInteractionTextEdit_ = nullptr;
    QPushButton *worldInteractionExecuteButton_ = nullptr;
    QComboBox *worldActionTypeCombo_ = nullptr;
    QLineEdit *worldActionTargetEdit_ = nullptr;
    QLineEdit *worldActionNpcEdit_ = nullptr;
    QLineEdit *worldActionLocationEdit_ = nullptr;
    QLineEdit *worldActionItemEdit_ = nullptr;
    QSpinBox *worldActionQuantitySpin_ = nullptr;
    QLineEdit *worldActionFlagEdit_ = nullptr;
    QCheckBox *worldActionConsumeCheck_ = nullptr;
    QCheckBox *worldActionFlagValueCheck_ = nullptr;
    QTextEdit *worldActionNoteEdit_ = nullptr;
    QPushButton *worldActionExecuteButton_ = nullptr;
    QTextEdit *worldActionResultText_ = nullptr;

    QPushButton *worldEventsRefreshButton_ = nullptr;
    QTableWidget *worldEventsTable_ = nullptr;
    QTextEdit *worldEventsRawText_ = nullptr;

    QComboBox *memoryTypeCombo_ = nullptr;
    QLineEdit *memorySearchEdit_ = nullptr;
    QPushButton *memoryRefreshButton_ = nullptr;
    QPushButton *memorySearchButton_ = nullptr;
    QLineEdit *memoryIdEdit_ = nullptr;
    QComboBox *memoryEditTypeCombo_ = nullptr;
    QLineEdit *memoryTagsEdit_ = nullptr;
    QSpinBox *memoryImportanceSpin_ = nullptr;
    QTextEdit *memoryTextEdit_ = nullptr;
    QPushButton *memoryCreateButton_ = nullptr;
    QPushButton *memoryUpdateButton_ = nullptr;
    QPushButton *memoryDeleteButton_ = nullptr;
    QPushButton *memoryNewButton_ = nullptr;
    QTableWidget *memoryTable_ = nullptr;
    QListWidget *memoryList_ = nullptr;

    QTableWidget *traceTable_ = nullptr;
    TraceTimelineWidget *traceTimeline_ = nullptr;
    QLabel *traceRequestLabel_ = nullptr;
    QTextEdit *traceMemoryText_ = nullptr;
    QTextEdit *traceDetailText_ = nullptr;
    QTextEdit *statusText_ = nullptr;
    QTimer *streamingRenderTimer_ = nullptr;
};
