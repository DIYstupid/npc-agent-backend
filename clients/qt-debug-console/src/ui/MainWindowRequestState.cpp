#include "MainWindow.h"

#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QTableWidget>

void MainWindow::updateRequestControls()
{
    if (requestStatusLabel_) {
        requestStatusLabel_->setText(requestTracker_.statusText());
    }

    if (healthButton_) {
        healthButton_->setEnabled(!requestTracker_.isBusy("health"));
    }
    if (cancelRequestsButton_) {
        cancelRequestsButton_->setEnabled(requestTracker_.isBusy());
    }
    if (refreshButton_) {
        refreshButton_->setEnabled(
            !requestTracker_.isBusy("list_npcs")
            && !requestTracker_.isBusy("game_state")
            && !requestTracker_.isBusy("quest_state")
            && !requestTracker_.isBusy("world_events")
            && !requestTracker_.isBusy("trace_list"));
    }

    const bool chatBusy = requestTracker_.isBusy("chat");
    const bool debugPromptBusy = requestTracker_.isBusy("debug_prompt");
    const bool conversationBusy = chatBusy || debugPromptBusy;
    if (messageEdit_) {
        messageEdit_->setEnabled(!conversationBusy);
    }
    if (sendButton_) {
        sendButton_->setEnabled(!conversationBusy);
    }
    if (cancelChatButton_) {
        cancelChatButton_->setEnabled(conversationBusy);
    }
    if (debugPromptButton_) {
        debugPromptButton_->setEnabled(!conversationBusy);
    }
    if (clearHistoryButton_) {
        clearHistoryButton_->setEnabled(!requestTracker_.isBusy("clear_chat_history"));
    }

    if (memoryRefreshButton_) {
        memoryRefreshButton_->setEnabled(!requestTracker_.isBusy("long_term_memory_list"));
    }
    if (memorySearchButton_) {
        memorySearchButton_->setEnabled(!requestTracker_.isBusy("long_term_memory_search"));
    }
    if (memoryCreateButton_) {
        memoryCreateButton_->setEnabled(!requestTracker_.isBusy("create_long_term_memory"));
    }
    if (memoryUpdateButton_) {
        memoryUpdateButton_->setEnabled(!requestTracker_.isBusy("update_long_term_memory"));
    }
    if (memoryDeleteButton_) {
        memoryDeleteButton_->setEnabled(!requestTracker_.isBusy("delete_long_term_memory"));
    }

    if (questRefreshButton_) {
        questRefreshButton_->setEnabled(!requestTracker_.isBusy("quest_state"));
    }
    if (worldInteractionExecuteButton_) {
        worldInteractionExecuteButton_->setEnabled(!requestTracker_.isBusy("world_interaction"));
    }
    if (worldActionExecuteButton_) {
        worldActionExecuteButton_->setEnabled(!requestTracker_.isBusy("world_action"));
    }
    if (worldEventsRefreshButton_) {
        worldEventsRefreshButton_->setEnabled(!requestTracker_.isBusy("world_events"));
    }

    if (traceTable_) {
        traceTable_->setEnabled(!requestTracker_.isBusy("trace_detail"));
    }
}
