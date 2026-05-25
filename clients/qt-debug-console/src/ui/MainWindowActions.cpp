#include "MainWindow.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDockWidget>
#include <QJsonArray>
#include <QJsonObject>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QSpinBox>
#include <QStringList>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTextEdit>
#include <QUrl>

#include "common/JsonUtils.h"

namespace {
constexpr int StaticCacheTtlMs = 300000;
constexpr int PanelCacheTtlMs = 60000;
constexpr int TraceCacheTtlMs = 300000;

QString cacheKey(const QStringList &parts)
{
    return parts.join("::");
}

QString normalizedMemoryType(const QString &memoryType)
{
    const QString trimmed = memoryType.trimmed();
    return trimmed.isEmpty() ? QString("<all>") : trimmed;
}
}

void MainWindow::applyBaseUrl()
{
    const QString baseUrlText = baseUrlEdit_->text().trimmed();
    if (!appliedBaseUrlText_.isEmpty() && baseUrlText != appliedBaseUrlText_) {
        cache_.clear();
    }

    appliedBaseUrlText_ = baseUrlText;
    api_.setBaseUrl(QUrl(baseUrlText));
}

void MainWindow::refreshAll(bool force)
{
    applyBaseUrl();
    requestNpcs(force);
    requestGameState(force);
    if (force || (questDock_ && questDock_->isVisible())) {
        requestQuests(force);
    }
    if (force || (worldEventsDock_ && worldEventsDock_->isVisible())) {
        requestWorldEvents(force);
    }
    if (force || (traceDock_ && traceDock_->isVisible())) {
        requestTraces(force);
    }
    refreshNpcScoped(force);
    refreshCurrentPanel(force);
}

void MainWindow::refreshNpcScoped(bool force)
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    applyBaseUrl();
    requestChatHistory(force);
    requestSummary(force);

    if (memoryDock_ && memoryDock_->isVisible()) {
        requestLongTermMemories(force);
    }
}

void MainWindow::refreshCurrentPanel(bool force)
{
    if (memoryDock_ && memoryDock_->isVisible()) {
        requestLongTermMemories(force);
    }
    if (traceDock_ && traceDock_->isVisible()) {
        requestTraces(force);
    }
    if (questDock_ && questDock_->isVisible()) {
        requestQuests(force);
    }
    if (worldEventsDock_ && worldEventsDock_->isVisible()) {
        requestWorldEvents(force);
    }
}

void MainWindow::sendChat()
{
    if (requestTracker_.isBusy("chat") || requestTracker_.isBusy("debug_prompt")) {
        return;
    }

    const QString message = messageEdit_->text().trimmed();
    const QString npcId = selectedNpcId();
    if (message.isEmpty() || npcId.isEmpty()) {
        return;
    }

    applyBaseUrl();
    finishStreamingChatRendering();
    pendingMessage_ = message;
    pendingMessageRendered_ = true;
    resetStreamingChatState();
    appendChatLine("player", message);
    messageEdit_->clear();
    api_.sendChatStream(npcId, playerId(), message);
}

void MainWindow::cancelConversationRequest()
{
    api_.cancelOperation("chat");
    api_.cancelOperation("debug_prompt");
}

void MainWindow::cancelAllRequests()
{
    api_.cancelAllRequests();
}

void MainWindow::requestDebugPrompt()
{
    if (requestTracker_.isBusy("debug_prompt") || requestTracker_.isBusy("chat")) {
        return;
    }

    const QString message = messageEdit_->text().trimmed().isEmpty()
        ? QString("debug")
        : messageEdit_->text().trimmed();
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    applyBaseUrl();
    api_.fetchDebugPrompt(npcId, playerId(), message);
}

void MainWindow::clearHistory()
{
    if (requestTracker_.isBusy("clear_chat_history")) {
        return;
    }

    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    applyBaseUrl();
    cache_.invalidate(cacheKey({"chat_history", playerId(), npcId}));
    api_.clearChatHistory(playerId(), npcId);
}

void MainWindow::refreshMemory(bool force)
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    applyBaseUrl();
    requestLongTermMemories(force);
}

void MainWindow::searchMemory(bool force)
{
    const QString npcId = selectedNpcId();
    const QString query = memorySearchEdit_->text().trimmed();
    if (npcId.isEmpty() || query.isEmpty()) {
        refreshMemory();
        return;
    }

    applyBaseUrl();
    requestLongTermMemorySearch(force);
}

void MainWindow::createMemory()
{
    if (requestTracker_.isBusy("create_long_term_memory")) {
        return;
    }

    const QString npcId = selectedNpcId();
    const QString text = memoryTextEdit_->toPlainText().trimmed();
    if (npcId.isEmpty() || text.isEmpty()) {
        return;
    }

    applyBaseUrl();
    api_.createLongTermMemory(
        npcId,
        playerId(),
        text,
        memoryEditTypeCombo_->currentText(),
        memoryImportanceSpin_->value(),
        memoryTags());
}

void MainWindow::updateMemory()
{
    if (requestTracker_.isBusy("update_long_term_memory")) {
        return;
    }

    const QString memoryId = selectedMemoryId();
    const QString text = memoryTextEdit_->toPlainText().trimmed();
    if (memoryId.isEmpty() || text.isEmpty()) {
        return;
    }

    applyBaseUrl();
    api_.updateLongTermMemory(
        memoryId,
        text,
        memoryEditTypeCombo_->currentText(),
        memoryImportanceSpin_->value(),
        memoryTags());
}

void MainWindow::deleteMemory()
{
    if (requestTracker_.isBusy("delete_long_term_memory")) {
        return;
    }

    const QString memoryId = selectedMemoryId();
    if (memoryId.isEmpty()) {
        return;
    }

    const auto answer = QMessageBox::question(
        this,
        "Delete memory",
        QString("Delete memory %1?").arg(memoryId),
        QMessageBox::Yes | QMessageBox::No,
        QMessageBox::No);
    if (answer != QMessageBox::Yes) {
        return;
    }

    applyBaseUrl();
    api_.deleteLongTermMemory(memoryId);
}

void MainWindow::executeWorldInteraction()
{
    if (requestTracker_.isBusy("world_interaction")) {
        return;
    }

    const QJsonObject payload = buildWorldInteractionPayload();
    if (payload.value("player_id").toString().isEmpty()
        || payload.value("text").toString().trimmed().isEmpty()) {
        appendStatus("world interaction skipped: player_id and text are required");
        return;
    }

    applyBaseUrl();
    api_.applyWorldInteraction(payload);
}

void MainWindow::executeWorldAction()
{
    if (requestTracker_.isBusy("world_action")) {
        return;
    }

    const QJsonObject payload = buildWorldActionPayload();
    if (payload.value("player_id").toString().isEmpty()
        || payload.value("action_type").toString().isEmpty()) {
        appendStatus("world action skipped: player_id and action_type are required");
        return;
    }

    applyBaseUrl();
    worldActionResultText_->setPlainText("Executing world action...");
    api_.applyWorldAction(payload);
}

void MainWindow::updateWorldActionForm()
{
    if (!worldActionTypeCombo_) {
        return;
    }

    const QString actionType = worldActionTypeCombo_->currentText();
    const bool usesItem = actionType == "pick_item"
        || actionType == "use_item"
        || actionType == "submit_item_to_npc";
    const bool usesNpc = actionType == "talk_to_npc"
        || actionType == "submit_item_to_npc";
    const bool usesLocation = true;
    const bool usesTarget = actionType == "inspect_object"
        || actionType == "defeat_enemy";
    const bool usesQuantity = actionType == "submit_item_to_npc";
    const bool usesConsume = actionType == "use_item";
    const bool usesFlag = true;

    if (worldActionTargetEdit_) {
        worldActionTargetEdit_->setEnabled(usesTarget);
        worldActionTargetEdit_->setPlaceholderText(actionType == "defeat_enemy" ? "enemy_id" : "target_id / object_id");
    }
    if (worldActionNpcEdit_) {
        worldActionNpcEdit_->setEnabled(usesNpc);
        worldActionNpcEdit_->setPlaceholderText(usesNpc ? "npc_id, blank uses selected NPC" : "not used");
    }
    if (worldActionLocationEdit_) {
        worldActionLocationEdit_->setEnabled(usesLocation);
        worldActionLocationEdit_->setPlaceholderText(actionType == "move" ? "destination location" : "optional event location");
    }
    if (worldActionItemEdit_) {
        worldActionItemEdit_->setEnabled(usesItem);
    }
    if (worldActionQuantitySpin_) {
        worldActionQuantitySpin_->setEnabled(usesQuantity);
    }
    if (worldActionConsumeCheck_) {
        worldActionConsumeCheck_->setEnabled(usesConsume);
    }
    if (worldActionFlagEdit_) {
        worldActionFlagEdit_->setEnabled(usesFlag);
        worldActionFlagEdit_->setPlaceholderText(actionType == "defeat_enemy" ? "blank uses defeated_<enemy_id>" : "optional world flag");
    }
    if (worldActionFlagValueCheck_) {
        worldActionFlagValueCheck_->setEnabled(usesFlag);
    }
}

void MainWindow::populateMemoryEditorFromSelection()
{
    const QList<QTableWidgetItem *> selectedItems = memoryTable_->selectedItems();
    if (selectedItems.isEmpty()) {
        return;
    }

    const int row = selectedItems.first()->row();
    memoryEditTypeCombo_->setCurrentText(memoryTable_->item(row, 0)->text());
    memoryImportanceSpin_->setValue(memoryTable_->item(row, 1)->text().toInt());
    memoryTagsEdit_->setText(memoryTable_->item(row, 2)->text());
    memoryTextEdit_->setPlainText(memoryTable_->item(row, 4)->text());
    memoryIdEdit_->setText(memoryTable_->item(row, 5)->text());
}

void MainWindow::populateMemoryEditorFromCard(QListWidgetItem *item)
{
    if (!item) {
        return;
    }

    const int row = item->data(Qt::UserRole).toInt();
    if (row < 0 || row >= currentMemories_.size()) {
        return;
    }

    const QJsonObject memory = currentMemories_.at(row).toObject();
    memoryEditTypeCombo_->setCurrentText(memory.value("memory_type").toString("general"));
    memoryImportanceSpin_->setValue(memory.value("importance").toInt(5));
    memoryTagsEdit_->setText(jsonArrayToStringList(memory.value("tags").toArray()).join(", "));
    memoryTextEdit_->setPlainText(memory.value("text").toString());
    memoryIdEdit_->setText(memory.value("memory_id").toString());
}

void MainWindow::requestSelectedTrace()
{
    if (suppressTraceSelectionFetch_) {
        return;
    }

    const QList<QTableWidgetItem *> selectedItems = traceTable_->selectedItems();
    if (selectedItems.isEmpty()) {
        return;
    }

    const QString requestId = traceRequestIdAtRow(selectedItems.first()->row());
    if (requestId.isEmpty() || requestId == activeTraceRequestId_) {
        return;
    }

    fetchTraceDetail(requestId);
}

void MainWindow::fetchTraceDetail(const QString &requestId, bool force)
{
    if (requestId.isEmpty()
        || requestId == pendingTraceRequestId_) {
        return;
    }

    const QString key = cacheKey({"trace_detail", requestId});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        pendingTraceRequestId_.clear();
        renderTraceDetail(cached.toObject());
        return;
    }

    if (requestTracker_.isBusy("trace_detail")) {
        return;
    }

    pendingTraceRequestId_ = requestId;
    applyBaseUrl();
    api_.fetchTrace(requestId);
}

void MainWindow::requestNpcs(bool force)
{
    const QString key = "npcs";
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onNpcsLoaded(cached.toArray());
        return;
    }

    if (!requestTracker_.isBusy("list_npcs")) {
        api_.fetchNpcs();
    }
}

void MainWindow::requestGameState(bool force)
{
    const QString key = cacheKey({"game_state", playerId()});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        renderStateTree(cached.toObject());
        return;
    }

    if (!requestTracker_.isBusy("game_state")) {
        api_.fetchGameState(playerId());
    }
}

void MainWindow::requestChatHistory(bool force)
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    const QString key = cacheKey({"chat_history", playerId(), npcId});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onChatHistoryLoaded(cached.toObject());
        return;
    }

    if (!requestTracker_.isBusy("chat_history")) {
        api_.fetchChatHistory(playerId(), npcId);
    }
}

void MainWindow::requestSummary(bool force)
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    const QString key = cacheKey({"summary", playerId(), npcId});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onSummaryLoaded(cached.toObject());
        return;
    }

    if (!requestTracker_.isBusy("summary_memory")) {
        api_.fetchSummary(playerId(), npcId);
    }
}

void MainWindow::requestQuests(bool force)
{
    const QString id = playerId();
    if (id.isEmpty()) {
        return;
    }

    const QString key = cacheKey({"quest_state", id});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onQuestsLoaded(cached.toObject());
        return;
    }

    if (!requestTracker_.isBusy("quest_state")) {
        api_.fetchQuests(id);
    }
}

void MainWindow::requestWorldEvents(bool force)
{
    const QString id = playerId();
    const QString key = cacheKey({"world_events", id, "50"});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onWorldEventsLoaded(cached.toArray());
        return;
    }

    if (!requestTracker_.isBusy("world_events")) {
        api_.fetchWorldEvents(id, 50);
    }
}

void MainWindow::requestLongTermMemories(bool force)
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    const QString memoryType = normalizedMemoryType(memoryTypeCombo_->currentText());
    const QString key = cacheKey({"memory_list", playerId(), npcId, memoryType});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onLongTermMemoriesLoaded(cached.toObject());
        return;
    }

    if (!requestTracker_.isBusy("long_term_memory_list")) {
        api_.fetchLongTermMemories(npcId, playerId(), memoryTypeCombo_->currentText());
    }
}

void MainWindow::requestLongTermMemorySearch(bool force)
{
    const QString npcId = selectedNpcId();
    const QString query = memorySearchEdit_->text().trimmed();
    if (npcId.isEmpty() || query.isEmpty()) {
        return;
    }

    const QString memoryType = normalizedMemoryType(memoryTypeCombo_->currentText());
    const QString key = cacheKey({"memory_search", playerId(), npcId, memoryType, query});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onLongTermSearchLoaded(cached.toArray());
        return;
    }

    if (!requestTracker_.isBusy("long_term_memory_search")) {
        api_.searchLongTermMemories(npcId, playerId(), query, memoryTypeCombo_->currentText());
    }
}

void MainWindow::requestTraces(bool force)
{
    const QString key = cacheKey({"trace_list", "20"});
    QJsonValue cached;
    if (!force && cache_.get(key, &cached)) {
        onTracesLoaded(cached.toArray());
        return;
    }

    if (!requestTracker_.isBusy("trace_list")) {
        api_.fetchTraces();
    }
}

void MainWindow::invalidateNpcScopedCache()
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    cache_.invalidate(cacheKey({"chat_history", playerId(), npcId}));
    cache_.invalidate(cacheKey({"summary", playerId(), npcId}));
}

void MainWindow::invalidateMemoryCache()
{
    const QString npcId = selectedNpcId();
    if (npcId.isEmpty()) {
        return;
    }

    cache_.invalidatePrefix(cacheKey({"memory_list", playerId(), npcId}));
    cache_.invalidatePrefix(cacheKey({"memory_search", playerId(), npcId}));
}

void MainWindow::invalidateQuestCache()
{
    cache_.invalidatePrefix(cacheKey({"quest_state", playerId()}));
}

void MainWindow::invalidateWorldEventsCache()
{
    cache_.invalidatePrefix(cacheKey({"world_events", playerId()}));
}

void MainWindow::invalidateTraceCache()
{
    cache_.invalidatePrefix("trace_list");
    cache_.invalidatePrefix("trace_detail");
}

QString MainWindow::selectedNpcId() const
{
    return npcCombo_->currentData().toString();
}

QString MainWindow::playerId() const
{
    return playerIdEdit_->text().trimmed();
}

QString MainWindow::selectedMemoryId() const
{
    return memoryIdEdit_->text().trimmed();
}

QJsonObject MainWindow::buildWorldInteractionPayload() const
{
    QJsonObject payload{
        {"player_id", playerId()},
        {"text", worldInteractionTextEdit_ ? worldInteractionTextEdit_->toPlainText().trimmed() : QString()},
    };

    const QString npcId = selectedNpcId();
    if (!npcId.isEmpty()) {
        payload.insert("npc_id", npcId);
    }

    return payload;
}

QJsonObject MainWindow::buildWorldActionPayload() const
{
    const QString actionType = worldActionTypeCombo_
        ? worldActionTypeCombo_->currentText().trimmed()
        : QString();
    const bool usesTarget = actionType == "inspect_object"
        || actionType == "defeat_enemy";
    const bool usesNpc = actionType == "talk_to_npc"
        || actionType == "submit_item_to_npc";
    const bool usesItem = actionType == "pick_item"
        || actionType == "use_item"
        || actionType == "submit_item_to_npc";
    const QString targetId = worldActionTargetEdit_
        ? worldActionTargetEdit_->text().trimmed()
        : QString();
    QString npcId = worldActionNpcEdit_
        ? worldActionNpcEdit_->text().trimmed()
        : QString();
    const QString location = worldActionLocationEdit_
        ? worldActionLocationEdit_->text().trimmed()
        : QString();
    const QString itemId = worldActionItemEdit_
        ? worldActionItemEdit_->text().trimmed()
        : QString();
    const QString flag = worldActionFlagEdit_
        ? worldActionFlagEdit_->text().trimmed()
        : QString();
    const QString note = worldActionNoteEdit_
        ? worldActionNoteEdit_->toPlainText().trimmed()
        : QString();

    if (npcId.isEmpty() && usesNpc) {
        npcId = selectedNpcId();
    }

    QJsonObject payload{
        {"player_id", playerId()},
        {"action_type", actionType},
    };
    if (usesTarget && !targetId.isEmpty()) {
        payload.insert("target_id", targetId);
    }
    if (usesNpc && !npcId.isEmpty()) {
        payload.insert("npc_id", npcId);
    }
    if (!location.isEmpty()) {
        payload.insert("location", location);
    }
    if (!note.isEmpty()) {
        payload.insert("note", note);
    }

    QJsonObject actionPayload;
    if (usesItem && !itemId.isEmpty()) {
        actionPayload.insert("item_id", itemId);
    }
    if (worldActionQuantitySpin_ && actionType == "submit_item_to_npc") {
        actionPayload.insert("quantity", worldActionQuantitySpin_->value());
    }
    if (worldActionConsumeCheck_ && actionType == "use_item") {
        actionPayload.insert("consume", worldActionConsumeCheck_->isChecked());
    }
    if (!flag.isEmpty()) {
        actionPayload.insert("flag", flag);
        if (worldActionFlagValueCheck_) {
            actionPayload.insert("value", worldActionFlagValueCheck_->isChecked());
        }
    }
    payload.insert("payload", actionPayload);

    return payload;
}

QStringList MainWindow::memoryTags() const
{
    QStringList tags;
    for (const QString &tag : memoryTagsEdit_->text().split(',', Qt::SkipEmptyParts)) {
        if (!tag.trimmed().isEmpty()) {
            tags.append(tag.trimmed());
        }
    }

    return tags;
}

QString MainWindow::traceRequestIdAtRow(int row) const
{
    if (row < 0 || row >= traceTable_->rowCount()) {
        return QString();
    }

    if (auto *requestItem = traceTable_->item(row, 0)) {
        return requestItem->text();
    }

    return QString();
}

void MainWindow::onNpcsLoaded(const QJsonArray &npcs)
{
    cache_.put("npcs", npcs, StaticCacheTtlMs);
    npcs_ = npcs;
    renderNpcTable(npcs);

    const QString previousNpc = pendingSelectedNpcId_.isEmpty()
        ? selectedNpcId()
        : pendingSelectedNpcId_;
    npcCombo_->blockSignals(true);
    npcCombo_->clear();

    for (const QJsonValue &value : npcs) {
        const QJsonObject npc = value.toObject();
        const QString label = QString("%1 (%2)")
            .arg(npc.value("name").toString(), npc.value("npc_id").toString());
        npcCombo_->addItem(label, npc.value("npc_id").toString());
    }

    const int previousIndex = npcCombo_->findData(previousNpc);
    if (previousIndex >= 0) {
        npcCombo_->setCurrentIndex(previousIndex);
    }
    pendingSelectedNpcId_.clear();
    npcCombo_->blockSignals(false);

    refreshNpcScoped();
}

void MainWindow::onGameStateLoaded(const QJsonObject &state)
{
    cache_.put(cacheKey({"game_state", playerId()}), state, PanelCacheTtlMs);
    renderStateTree(state);
}

void MainWindow::onChatHistoryLoaded(const QJsonObject &history)
{
    const QString npcId = selectedNpcId();
    if (!npcId.isEmpty()) {
        cache_.put(cacheKey({"chat_history", playerId(), npcId}), history, PanelCacheTtlMs);
    }

    chatView_->clear();
    const QJsonArray messages = history.value("messages").toArray();
    for (const QJsonValue &value : messages) {
        const QJsonObject message = value.toObject();
        appendChatLine(message.value("role").toString(), message.value("content").toString());
    }
}

void MainWindow::onChatLoaded(const QJsonObject &chatResponse)
{
    if (!pendingMessage_.isEmpty()) {
        if (!pendingMessageRendered_) {
            appendChatLine("player", pendingMessage_);
        }
        pendingMessage_.clear();
        pendingMessageRendered_ = false;
    }

    const bool hasStreamingReply =
        streamingReplyActive_ || !streamingReply_.isEmpty() || !streamingRenderQueue_.isEmpty();
    if (!hasStreamingReply) {
        appendChatLine("npc", chatResponse.value("reply").toString());
        resetStreamingChatState();
    } else {
        streamingFinalReceived_ = true;
        if (streamingRenderQueue_.isEmpty()) {
            resetStreamingChatState();
        }
    }
    renderContextReport(chatResponse.value("context_report").toObject());
    renderActions(
        chatResponse.value("actions").toArray(),
        chatResponse.value("executed_actions").toArray());
    rawResponseText_->setPlainText(formatJsonObject(chatResponse));

    invalidateNpcScopedCache();
    invalidateMemoryCache();
    invalidateQuestCache();
    invalidateWorldEventsCache();
    invalidateTraceCache();
    cache_.invalidate(cacheKey({"game_state", playerId()}));

    requestGameState(true);
    requestSummary(true);
    requestLongTermMemories(true);
    requestQuests(true);
    requestWorldEvents(true);
    api_.fetchLatestTrace();
    requestTraces(true);
}

void MainWindow::onChatStreamStarted(const QJsonObject &payload)
{
    appendStatus(QString("chat stream started: %1").arg(payload.value("request_id").toString()));
}

void MainWindow::onChatStreamDelta(const QString &text)
{
    appendStreamingChatDelta(text);
}

void MainWindow::onDebugPromptLoaded(const QJsonObject &debugPrompt)
{
    promptText_->setPlainText(debugPrompt.value("prompt").toString());
    renderContextReport(debugPrompt.value("context_report").toObject());
    rawResponseText_->setPlainText(formatJsonObject(debugPrompt));
}

void MainWindow::onLongTermMemoriesLoaded(const QJsonObject &payload)
{
    const QString npcId = selectedNpcId();
    if (!npcId.isEmpty()) {
        const QString memoryType = normalizedMemoryType(memoryTypeCombo_->currentText());
        cache_.put(cacheKey({"memory_list", playerId(), npcId, memoryType}), payload, PanelCacheTtlMs);
    }

    renderMemories(payload.value("memories").toArray());
}

void MainWindow::onLongTermSearchLoaded(const QJsonArray &memories)
{
    const QString npcId = selectedNpcId();
    const QString query = memorySearchEdit_->text().trimmed();
    if (!npcId.isEmpty() && !query.isEmpty()) {
        const QString memoryType = normalizedMemoryType(memoryTypeCombo_->currentText());
        cache_.put(cacheKey({"memory_search", playerId(), npcId, memoryType, query}), memories, PanelCacheTtlMs);
    }

    renderMemories(memories);
}

void MainWindow::onSummaryLoaded(const QJsonObject &summary)
{
    const QString npcId = selectedNpcId();
    if (!npcId.isEmpty()) {
        cache_.put(cacheKey({"summary", playerId(), npcId}), summary, PanelCacheTtlMs);
    }

    summaryText_->setPlainText(summary.value("summary").toString());
}

void MainWindow::onQuestsLoaded(const QJsonObject &quests)
{
    cache_.put(cacheKey({"quest_state", playerId()}), quests, PanelCacheTtlMs);
    renderQuests(quests);
}

void MainWindow::onWorldInteractionApplied(const QJsonObject &response)
{
    renderWorldInteractionResult(response);
    renderActions(QJsonArray(), response.value("executed_actions").toArray());
    rawResponseText_->setPlainText(formatJsonObject(response));

    const QJsonObject playerState = response.value("player_state").toObject();
    if (!playerState.isEmpty()) {
        cache_.put(cacheKey({"game_state", playerId()}), playerState, PanelCacheTtlMs);
        renderStateTree(playerState);
    }

    invalidateQuestCache();
    invalidateWorldEventsCache();
    invalidateTraceCache();
    cache_.invalidate(cacheKey({"game_state", playerId()}));

    requestGameState(true);
    requestQuests(true);
    requestWorldEvents(true);
    api_.fetchLatestTrace();
    requestTraces(true);
}

void MainWindow::onWorldActionApplied(const QJsonObject &response)
{
    renderWorldActionResult(response);
    renderActions(QJsonArray(), response.value("executed_actions").toArray());
    rawResponseText_->setPlainText(formatJsonObject(response));

    const QJsonObject playerState = response.value("player_state").toObject();
    if (!playerState.isEmpty()) {
        cache_.put(cacheKey({"game_state", playerId()}), playerState, PanelCacheTtlMs);
        renderStateTree(playerState);
    }

    invalidateQuestCache();
    invalidateWorldEventsCache();
    invalidateTraceCache();
    cache_.invalidate(cacheKey({"game_state", playerId()}));

    requestGameState(true);
    requestQuests(true);
    requestWorldEvents(true);
    api_.fetchLatestTrace();
    requestTraces(true);
}

void MainWindow::onWorldEventsLoaded(const QJsonArray &events)
{
    cache_.put(cacheKey({"world_events", playerId(), "50"}), events, PanelCacheTtlMs);
    renderWorldEvents(events);
}

void MainWindow::onTracesLoaded(const QJsonArray &traces)
{
    cache_.put(cacheKey({"trace_list", "20"}), traces, PanelCacheTtlMs);
    renderTraces(traces);
}

void MainWindow::onTraceLoaded(const QJsonObject &trace)
{
    const QString requestId = trace.value("request_id").toString();
    if (!pendingTraceRequestId_.isEmpty() && requestId != pendingTraceRequestId_) {
        appendStatus(QString("ignored stale trace response: %1").arg(requestId));
        return;
    }

    if (requestId == pendingTraceRequestId_) {
        pendingTraceRequestId_.clear();
    }

    if (!requestId.isEmpty()) {
        cache_.put(cacheKey({"trace_detail", requestId}), trace, TraceCacheTtlMs);
    }

    renderTraceDetail(trace);
}

void MainWindow::onRequestCancelled(const QString &operation)
{
    if (operation == "chat" && !pendingMessage_.isEmpty()) {
        if (messageEdit_->text().trimmed().isEmpty()) {
            messageEdit_->setText(pendingMessage_);
        }
        pendingMessage_.clear();
        pendingMessageRendered_ = false;
        resetStreamingChatState();
    }

    if (operation == "trace_detail") {
        pendingTraceRequestId_.clear();
    }

    if (operation == "world_action" && worldActionResultText_) {
        worldActionResultText_->setPlainText("World action cancelled.");
    }
    if (operation == "world_interaction" && worldActionResultText_) {
        worldActionResultText_->append("World interaction cancelled.");
    }

    appendStatus(QString("%1 cancelled").arg(operation));
}

void MainWindow::onApiError(const QString &operation, const QString &message, int statusCode)
{
    if (operation == "chat" && !pendingMessage_.isEmpty()) {
        if (messageEdit_->text().trimmed().isEmpty()) {
            messageEdit_->setText(pendingMessage_);
        }
        pendingMessage_.clear();
        pendingMessageRendered_ = false;
        resetStreamingChatState();
    }

    if (operation == "trace_detail") {
        pendingTraceRequestId_.clear();
    }

    if (operation == "world_action" && worldActionResultText_) {
        worldActionResultText_->setPlainText(QString("World action failed (%1): %2").arg(statusCode).arg(message));
    }
    if (operation == "world_interaction" && worldActionResultText_) {
        worldActionResultText_->append(QString("World interaction failed (%1): %2").arg(statusCode).arg(message));
    }

    appendStatus(QString("%1 failed (%2): %3").arg(operation).arg(statusCode).arg(message));
}

