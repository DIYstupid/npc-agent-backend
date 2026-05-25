#include "MainWindow.h"

#include <QDateTime>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QLayout>
#include <QListWidget>
#include <QListWidgetItem>
#include <QProgressBar>
#include <QSignalBlocker>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTextCursor>
#include <QTextEdit>
#include <QTimer>
#include <QTreeWidget>
#include <QTreeWidgetItem>
#include <QtGlobal>

#include "common/JsonUtils.h"
#include "ui/widgets/TraceTimelineWidget.h"
#include "ui/widgets/TokenBudgetChart.h"

namespace {
constexpr int TypeRole = Qt::UserRole + 1;
constexpr int ImportanceRole = Qt::UserRole + 2;
constexpr int TagsRole = Qt::UserRole + 3;
constexpr int TextRole = Qt::UserRole + 4;
constexpr int CreatedRole = Qt::UserRole + 5;

QTableWidgetItem *item(const QString &text)
{
    auto *tableItem = new QTableWidgetItem(text);
    tableItem->setFlags(tableItem->flags() & ~Qt::ItemIsEditable);
    return tableItem;
}

QTableWidgetItem *jsonItem(const QJsonValue &value)
{
    return item(jsonValueToDisplayString(value));
}

void appendHistoryEntry(QTextEdit *textEdit, const QString &title, const QStringList &lines)
{
    const QString timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");
    QStringList entry;
    entry.append(QString("[%1] %2").arg(timestamp, title));
    entry.append(lines);

    const QString previous = textEdit->toPlainText().trimmed();
    const QString body = entry.join('\n');
    textEdit->setPlainText(previous.isEmpty() ? body : previous + "\n\n---\n" + body);
    textEdit->moveCursor(QTextCursor::End);
}
}
void MainWindow::renderNpcTable(const QJsonArray &npcs)
{
    npcTable_->setRowCount(npcs.size());
    int row = 0;
    for (const QJsonValue &value : npcs) {
        const QJsonObject npc = value.toObject();
        npcTable_->setItem(row, 0, jsonItem(npc.value("npc_id")));
        npcTable_->setItem(row, 1, jsonItem(npc.value("name")));
        npcTable_->setItem(row, 2, jsonItem(npc.value("role")));
        npcTable_->setItem(row, 3, jsonItem(npc.value("faction")));
        npcTable_->setItem(row, 4, jsonItem(npc.value("location")));
        ++row;
    }
}

void MainWindow::renderStateTree(const QJsonObject &state)
{
    stateTree_->clear();

    for (auto it = state.constBegin(); it != state.constEnd(); ++it) {
        addJsonToTree(nullptr, it.key(), it.value());
    }

    stateTree_->expandAll();
}

void MainWindow::renderContextReport(const QJsonObject &report)
{
    contextTable_->clearContents();
    updateTokenUsage(report);
    if (tokenBudgetChart_) {
        tokenBudgetChart_->setReport(report);
    }

    QStringList keys{
        "request_id",
        "token_budget",
        "estimated_prompt_tokens",
        "estimated_saved_tokens",
        "selected_short_term_messages",
        "trimmed_short_term_messages",
        "selected_long_term_memories",
        "trimmed_long_term_memories",
        "has_summary_memory",
        "section_tokens",
    };

    contextTable_->setRowCount(keys.size());
    for (int row = 0; row < keys.size(); ++row) {
        const QString key = keys.at(row);
        contextTable_->setItem(row, 0, item(key));
        contextTable_->setItem(row, 1, jsonItem(report.value(key)));
    }

    const QJsonObject sectionTokens = report.value("section_tokens").toObject();
    sectionTokenTable_->clearContents();
    sectionTokenTable_->setRowCount(sectionTokens.size());

    int sectionRow = 0;
    for (auto it = sectionTokens.constBegin(); it != sectionTokens.constEnd(); ++it) {
        sectionTokenTable_->setItem(sectionRow, 0, item(it.key()));
        sectionTokenTable_->setItem(sectionRow, 1, jsonItem(it.value()));
        ++sectionRow;
    }
}

void MainWindow::renderActions(const QJsonArray &actions, const QJsonArray &executedActions)
{
    actionTable_->clearContents();
    actionTable_->setRowCount(actions.size() + executedActions.size());

    int row = 0;
    for (const QJsonValue &value : actions) {
        const QJsonObject action = value.toObject();
        actionTable_->setItem(row, 0, item("planned"));
        actionTable_->setItem(row, 1, jsonItem(action.value("tool")));
        actionTable_->setItem(row, 2, item(""));
        actionTable_->setItem(row, 3, item(""));
        actionTable_->setItem(row, 4, jsonItem(action.value("args")));
        ++row;
    }

    for (const QJsonValue &value : executedActions) {
        const QJsonObject action = value.toObject();
        const QJsonObject data = action.value("data").toObject();
        actionTable_->setItem(row, 0, item("executed"));
        actionTable_->setItem(row, 1, jsonItem(action.value("tool")));
        actionTable_->setItem(row, 2, jsonItem(action.value("success")));
        actionTable_->setItem(row, 3, jsonItem(data.value("status")));
        actionTable_->setItem(row, 4, item(action.value("message").toString() + "\n" + formatJsonObject(data)));
        ++row;
    }
}

void MainWindow::renderQuests(const QJsonObject &quests)
{
    const QStringList activeQuests = jsonArrayToStringList(quests.value("active_quests").toArray());
    const QStringList completedQuests = jsonArrayToStringList(quests.value("completed_quests").toArray());
    const QJsonObject progressByQuest = quests.value("quest_progress").toObject();

    QStringList questIds;
    auto appendQuestId = [&questIds](const QString &questId) {
        if (!questId.isEmpty() && !questIds.contains(questId)) {
            questIds.append(questId);
        }
    };
    for (auto it = progressByQuest.constBegin(); it != progressByQuest.constEnd(); ++it) {
        appendQuestId(it.key());
    }
    for (const QString &questId : activeQuests) {
        appendQuestId(questId);
    }
    for (const QString &questId : completedQuests) {
        appendQuestId(questId);
    }

    questTable_->clearContents();
    questTable_->setRowCount(questIds.size());

    int objectiveRows = 0;
    for (const QString &questId : questIds) {
        objectiveRows += progressByQuest.value(questId).toObject().value("objectives").toArray().size();
    }
    questObjectiveTable_->clearContents();
    questObjectiveTable_->setRowCount(objectiveRows);

    int questRow = 0;
    int objectiveRow = 0;
    for (const QString &questId : questIds) {
        const QJsonObject progress = progressByQuest.value(questId).toObject();
        const QJsonArray objectives = progress.value("objectives").toArray();
        const bool hasProgress = !progress.isEmpty();
        QString status = progress.value("status").toString();
        if (status.isEmpty()) {
            status = completedQuests.contains(questId) ? "completed" : "active";
        }

        int completedCount = 0;
        for (const QJsonValue &value : objectives) {
            if (value.toObject().value("status").toString() == "completed") {
                ++completedCount;
            }
        }
        const int remainingCount = objectives.size() - completedCount;

        questTable_->setItem(questRow, 0, item(questId));
        questTable_->setItem(questRow, 1, item(status));
        questTable_->setItem(questRow, 2, item(QString::number(objectives.size())));
        questTable_->setItem(questRow, 3, item(QString::number(completedCount)));
        questTable_->setItem(questRow, 4, item(QString::number(remainingCount)));
        questTable_->setItem(questRow, 5, item(hasProgress ? "quest_progress" : "quest list"));
        ++questRow;

        for (const QJsonValue &value : objectives) {
            const QJsonObject objective = value.toObject();
            QString target = objective.value("item_id").toString();
            if (target.isEmpty()) {
                target = objective.value("target_id").toString();
            }
            if (target.isEmpty()) {
                target = objective.value("flag").toString();
            }

            questObjectiveTable_->setItem(objectiveRow, 0, item(questId));
            questObjectiveTable_->setItem(objectiveRow, 1, jsonItem(objective.value("objective_id")));
            questObjectiveTable_->setItem(objectiveRow, 2, jsonItem(objective.value("status")));
            questObjectiveTable_->setItem(objectiveRow, 3, jsonItem(objective.value("type")));
            questObjectiveTable_->setItem(objectiveRow, 4, item(target));
            questObjectiveTable_->setItem(objectiveRow, 5, jsonItem(objective.value("npc_id")));
            questObjectiveTable_->setItem(objectiveRow, 6, jsonItem(objective.value("location")));
            questObjectiveTable_->setItem(objectiveRow, 7, jsonItem(objective.value("quantity")));
            questObjectiveTable_->setItem(objectiveRow, 8, jsonItem(objective.value("description")));
            ++objectiveRow;
        }
    }

    questRawText_->setPlainText(formatJsonObject(quests));
}

void MainWindow::renderWorldInteractionResult(const QJsonObject &response)
{
    QStringList lines;
    lines.append(QString("Status: %1").arg(response.value("status").toString()));
    lines.append(QString("Message: %1").arg(response.value("message").toString()));
    lines.append(QString("Request: %1").arg(response.value("request_id").toString()));

    const QJsonArray parsedActions = response.value("parsed_actions").toArray();
    if (!parsedActions.isEmpty()) {
        lines.append("");
        lines.append("Parsed Actions");
        for (const QJsonValue &value : parsedActions) {
            const QJsonObject action = value.toObject();
            lines.append(QString("  %1 %2 %3")
                .arg(
                    action.value("action_type").toString(),
                    action.value("target_id").toString(),
                    action.value("npc_id").toString())
                .trimmed());
        }
    }

    const QJsonArray questUpdates = response.value("quest_updates").toArray();
    if (!questUpdates.isEmpty()) {
        lines.append("");
        lines.append("Quest Updates");
        for (const QJsonValue &value : questUpdates) {
            const QJsonObject update = value.toObject();
            lines.append(QString("  %1: %2 (%3)")
                .arg(
                    update.value("quest_id").toString(),
                    update.value("status").toString(),
                    update.value("message").toString()));
            const QString completed = jsonArrayToStringList(update.value("completed_objectives").toArray()).join(", ");
            const QString remaining = jsonArrayToStringList(update.value("remaining_objectives").toArray()).join(", ");
            if (!completed.isEmpty()) {
                lines.append(QString("    completed: %1").arg(completed));
            }
            if (!remaining.isEmpty()) {
                lines.append(QString("    remaining: %1").arg(remaining));
            }
        }
    }

    lines.append("");
    lines.append(formatJsonObject(response));
    appendHistoryEntry(worldActionResultText_, "World Interaction", lines);
}

void MainWindow::renderWorldActionResult(const QJsonObject &response)
{
    QStringList lines;
    lines.append(QString("Status: %1").arg(response.value("status").toString()));
    lines.append(QString("Message: %1").arg(response.value("message").toString()));
    lines.append(QString("Request: %1").arg(response.value("request_id").toString()));

    const QJsonArray questUpdates = response.value("quest_updates").toArray();
    if (!questUpdates.isEmpty()) {
        lines.append("");
        lines.append("Quest Updates");
        for (const QJsonValue &value : questUpdates) {
            const QJsonObject update = value.toObject();
            lines.append(QString("  %1: %2 (%3)")
                .arg(
                    update.value("quest_id").toString(),
                    update.value("status").toString(),
                    update.value("message").toString()));
        }
    }

    lines.append("");
    lines.append(formatJsonObject(response));
    appendHistoryEntry(worldActionResultText_, "Structured World Action", lines);
}

void MainWindow::renderWorldEvents(const QJsonArray &events)
{
    worldEventsTable_->clearContents();
    worldEventsTable_->setRowCount(events.size());

    int row = 0;
    for (const QJsonValue &value : events) {
        const QJsonObject event = value.toObject();
        worldEventsTable_->setItem(row, 0, jsonItem(event.value("created_at")));
        worldEventsTable_->setItem(row, 1, jsonItem(event.value("event_type")));
        worldEventsTable_->setItem(row, 2, jsonItem(event.value("status")));
        worldEventsTable_->setItem(row, 3, jsonItem(event.value("location")));
        worldEventsTable_->setItem(row, 4, jsonItem(event.value("player_id")));
        worldEventsTable_->setItem(row, 5, jsonItem(event.value("source_npc_id")));
        worldEventsTable_->setItem(row, 6, item(jsonArrayToStringList(event.value("subject_npc_ids").toArray()).join(", ")));
        worldEventsTable_->setItem(row, 7, jsonItem(event.value("confidence")));
        worldEventsTable_->setItem(row, 8, jsonItem(event.value("text")));
        ++row;
    }

    worldEventsRawText_->setPlainText(formatJsonArray(events));
}

void MainWindow::renderMemories(const QJsonArray &memories)
{
    currentMemories_ = memories;
    memoryTable_->clearContents();
    memoryTable_->setRowCount(memories.size());
    memoryList_->clear();

    int row = 0;
    for (const QJsonValue &value : memories) {
        const QJsonObject memory = value.toObject();
        const QString type = memory.value("memory_type").toString("general");
        const int importance = memory.value("importance").toInt();
        const QString tags = jsonArrayToStringList(memory.value("tags").toArray()).join(", ");
        const QString created = memory.value("created_at").toString();
        const QString text = memory.value("text").toString();
        const QString memoryId = memory.value("memory_id").toString();

        memoryTable_->setItem(row, 0, jsonItem(memory.value("memory_type")));
        memoryTable_->setItem(row, 1, jsonItem(memory.value("importance")));
        memoryTable_->setItem(row, 2, item(tags));
        memoryTable_->setItem(row, 3, jsonItem(memory.value("created_at")));
        memoryTable_->setItem(row, 4, jsonItem(memory.value("text")));
        memoryTable_->setItem(row, 5, jsonItem(memory.value("memory_id")));

        auto *listItem = new QListWidgetItem();
        listItem->setText(text);
        listItem->setData(Qt::UserRole, row);
        listItem->setData(TypeRole, type);
        listItem->setData(ImportanceRole, importance);
        listItem->setData(TagsRole, tags);
        listItem->setData(TextRole, text);
        listItem->setData(CreatedRole, created);
        listItem->setToolTip(QString("%1\n%2").arg(memoryId, text));
        memoryList_->addItem(listItem);
        ++row;
    }
}

void MainWindow::renderTraces(const QJsonArray &traces)
{
    currentTraces_ = traces;
    suppressTraceSelectionFetch_ = true;
    traceTable_->clearContents();
    traceTable_->setRowCount(traces.size());
    if (traceTimeline_) {
        traceTimeline_->setTraces(traces);
    }

    int row = 0;
    for (const QJsonValue &value : traces) {
        const QJsonObject trace = value.toObject();
        traceTable_->setItem(row, 0, jsonItem(trace.value("request_id")));
        traceTable_->setItem(row, 1, jsonItem(trace.value("agent_type")));
        traceTable_->setItem(row, 2, jsonItem(trace.value("npc_id")));
        traceTable_->setItem(row, 3, jsonItem(trace.value("player_id")));
        traceTable_->setItem(row, 4, jsonItem(trace.value("estimated_prompt_tokens")));
        traceTable_->setItem(row, 5, item(QString("%1/%2")
            .arg(trace.value("actions_count").toInt())
            .arg(trace.value("executed_actions_count").toInt())));
        traceTable_->setItem(row, 6, jsonItem(trace.value("elapsed_ms")));
        traceTable_->setItem(row, 7, jsonItem(trace.value("error")));
        traceTable_->setItem(row, 8, jsonItem(trace.value("message_preview")));
        ++row;
    }
    suppressTraceSelectionFetch_ = false;

    if (!activeTraceRequestId_.isEmpty()) {
        for (int activeRow = 0; activeRow < traceTable_->rowCount(); ++activeRow) {
            if (traceRequestIdAtRow(activeRow) == activeTraceRequestId_) {
                selectTraceRow(activeTraceRequestId_);
                return;
            }
        }
    }

    if (traceTable_->rowCount() > 0) {
        traceTable_->selectRow(0);
        const QString requestId = traceRequestIdAtRow(0);
        if (!requestId.isEmpty()) {
            fetchTraceDetail(requestId);
        }
    }
}

void MainWindow::renderTraceDetail(const QJsonObject &trace)
{
    activeTraceRequestId_ = trace.value("request_id").toString();
    traceRequestLabel_->setText(QString("Selected trace: %1").arg(activeTraceRequestId_));
    if (traceTimeline_) {
        traceTimeline_->setActiveRequestId(activeTraceRequestId_);
    }
    traceDetailText_->setPlainText(formatJsonObject(trace));
    promptText_->setPlainText(trace.value("prompt").toString());
    renderContextReport(trace.value("context_report").toObject());
    renderActions(
        trace.value("actions").toArray(),
        trace.value("executed_actions").toArray());
    renderTraceMemoryHits(trace);
    selectTraceRow(activeTraceRequestId_);
}

void MainWindow::renderTraceMemoryHits(const QJsonObject &trace)
{
    QStringList lines;
    const QString summary = trace.value("summary_memory").toString();
    lines.append("Summary Memory");
    lines.append(summary.isEmpty() ? "  <empty>" : "  " + summary);
    lines.append("");

    lines.append("Selected Short-Term Memory");
    const QJsonArray shortMemory = trace.value("selected_short_term_memory").toArray();
    if (shortMemory.isEmpty()) {
        lines.append("  <empty>");
    } else {
        for (const QJsonValue &value : shortMemory) {
            const QJsonObject message = value.toObject();
            lines.append(QString("  [%1] %2")
                .arg(message.value("role").toString(), message.value("content").toString()));
        }
    }
    lines.append("");

    lines.append("Selected Long-Term Memory");
    const QJsonArray longMemory = trace.value("selected_long_term_memory").toArray();
    if (longMemory.isEmpty()) {
        lines.append("  <empty>");
    } else {
        for (const QJsonValue &value : longMemory) {
            const QJsonObject memory = value.toObject();
            lines.append(QString("  [%1|%2] %3")
                .arg(
                    memory.value("memory_type").toString("general"),
                    QString::number(memory.value("importance").toInt()),
                    memory.value("text").toString()));
        }
    }

    traceMemoryText_->setPlainText(lines.join('\n'));
}

void MainWindow::updateTokenUsage(const QJsonObject &report)
{
    const int budget = report.value("token_budget").toInt();
    const int used = report.value("estimated_prompt_tokens").toInt();
    const int saved = report.value("estimated_saved_tokens").toInt();
    const int percent = budget > 0 ? qMin(100, qRound((used * 100.0) / budget)) : 0;

    tokenUsageBar_->setValue(percent);
    tokenUsageLabel_->setText(QString("Context window: %1 / %2 tokens (%3%), saved %4")
        .arg(used)
        .arg(budget)
        .arg(percent)
        .arg(saved));
    contextWindowLabel_->setText(QString("Memory use: short-term %1/%2, long-term %3/%4, summary %5")
        .arg(report.value("selected_short_term_messages").toInt())
        .arg(report.value("trimmed_short_term_messages").toInt())
        .arg(report.value("selected_long_term_memories").toInt())
        .arg(report.value("trimmed_long_term_memories").toInt())
        .arg(report.value("has_summary_memory").toBool() ? "yes" : "no"));
    tokenUsageLabel_->updateGeometry();
    contextWindowLabel_->updateGeometry();
    if (tokenUsageLabel_->parentWidget() && tokenUsageLabel_->parentWidget()->layout()) {
        tokenUsageLabel_->parentWidget()->layout()->activate();
    }

    if (percent >= 90) {
        tokenUsageBar_->setStyleSheet("QProgressBar::chunk { background-color: #b3261e; }");
    } else if (percent >= 70) {
        tokenUsageBar_->setStyleSheet("QProgressBar::chunk { background-color: #b06000; }");
    } else {
        tokenUsageBar_->setStyleSheet("QProgressBar::chunk { background-color: #256f4a; }");
    }
}

void MainWindow::selectTraceRow(const QString &requestId)
{
    if (requestId.isEmpty()) {
        return;
    }

    QSignalBlocker blocker(traceTable_);
    for (int row = 0; row < traceTable_->rowCount(); ++row) {
        if (traceRequestIdAtRow(row) == requestId) {
            traceTable_->selectRow(row);
            return;
        }
    }
}

void MainWindow::appendChatLine(const QString &speaker, const QString &text)
{
    const QString label = speaker == "npc" ? "NPC" : "Player";
    chatView_->append(QString("<b>%1</b>: %2").arg(label, text.toHtmlEscaped()));
}

void MainWindow::appendStreamingChatDelta(const QString &text)
{
    if (text.isEmpty()) {
        return;
    }

    if (!streamingReplyActive_) {
        streamingReplyActive_ = true;
        streamingReply_.clear();
        chatView_->append("<b>NPC</b>: ");
    }

    streamingRenderQueue_.append(text);

    if (streamingRenderTimer_ && !streamingRenderTimer_->isActive()) {
        streamingRenderTimer_->start();
    }
}

void MainWindow::renderNextStreamingChatCharacter()
{
    if (streamingRenderQueue_.isEmpty()) {
        if (streamingRenderTimer_) {
            streamingRenderTimer_->stop();
        }
        if (streamingFinalReceived_) {
            resetStreamingChatState();
        }
        return;
    }

    const QString text = streamingRenderQueue_.left(1);
    streamingRenderQueue_.remove(0, 1);
    streamingReply_.append(text);

    QTextCursor cursor = chatView_->textCursor();
    cursor.movePosition(QTextCursor::End);
    cursor.insertText(text);
    chatView_->setTextCursor(cursor);

    if (streamingRenderQueue_.isEmpty() && streamingFinalReceived_) {
        resetStreamingChatState();
    }
}

void MainWindow::finishStreamingChatRendering()
{
    if (streamingRenderTimer_) {
        streamingRenderTimer_->stop();
    }

    while (!streamingRenderQueue_.isEmpty()) {
        const QString text = streamingRenderQueue_.left(1);
        streamingRenderQueue_.remove(0, 1);
        streamingReply_.append(text);

        QTextCursor cursor = chatView_->textCursor();
        cursor.movePosition(QTextCursor::End);
        cursor.insertText(text);
        chatView_->setTextCursor(cursor);
    }

    if (streamingFinalReceived_) {
        resetStreamingChatState();
    }
}

void MainWindow::resetStreamingChatState()
{
    if (streamingRenderTimer_) {
        streamingRenderTimer_->stop();
    }
    streamingReplyActive_ = false;
    streamingReply_.clear();
    streamingRenderQueue_.clear();
    streamingFinalReceived_ = false;
}

void MainWindow::appendStatus(const QString &line)
{
    const QString timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");
    statusText_->append(QString("[%1] %2").arg(timestamp, line.toHtmlEscaped()));
}

void MainWindow::addJsonToTree(QTreeWidgetItem *parent, const QString &key, const QJsonValue &value)
{
    auto *node = new QTreeWidgetItem(QStringList{key});
    if (parent) {
        parent->addChild(node);
    } else {
        stateTree_->addTopLevelItem(node);
    }

    if (value.isObject()) {
        const QJsonObject object = value.toObject();
        for (auto it = object.constBegin(); it != object.constEnd(); ++it) {
            addJsonToTree(node, it.key(), it.value());
        }
        return;
    }

    if (value.isArray()) {
        const QJsonArray array = value.toArray();
        for (int index = 0; index < array.size(); ++index) {
            addJsonToTree(node, QString("[%1]").arg(index), array.at(index));
        }
        return;
    }

    node->setText(1, jsonValueToDisplayString(value));
}

