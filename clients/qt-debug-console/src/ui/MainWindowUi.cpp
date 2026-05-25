#include "MainWindow.h"

#include <QAbstractItemView>
#include <QAbstractScrollArea>
#include <QAction>
#include <QCheckBox>
#include <QComboBox>
#include <QDockWidget>
#include <QFontMetrics>
#include <QFormLayout>
#include <QFrame>
#include <QGridLayout>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMenu>
#include <QMenuBar>
#include <QProgressBar>
#include <QPushButton>
#include <QScrollArea>
#include <QSizePolicy>
#include <QSplitter>
#include <QSpinBox>
#include <QStatusBar>
#include <QTabWidget>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTextEdit>
#include <QTreeWidget>
#include <QUrl>
#include <QVBoxLayout>
#include <QWidget>

#include "common/JsonUtils.h"
#include "ui/widgets/MemoryCardDelegate.h"
#include "ui/widgets/TraceTimelineWidget.h"
#include "ui/widgets/TokenBudgetChart.h"

namespace {
QStringList memoryTypes()
{
    return {
        "",
        "general",
        "profile",
        "quest",
        "relationship",
        "world_event",
    };
}

QStringList worldActionTypes()
{
    return {
        "move",
        "pick_item",
        "use_item",
        "submit_item_to_npc",
        "talk_to_npc",
        "inspect_object",
        "defeat_enemy",
    };
}

QScrollArea *wrapDockPanel(QWidget *content, QWidget *parent)
{
    content->setMinimumSize(0, 0);
    content->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Preferred);

    auto *scrollArea = new QScrollArea(parent);
    scrollArea->setWidget(content);
    scrollArea->setWidgetResizable(true);
    scrollArea->setFrameShape(QFrame::NoFrame);
    scrollArea->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    scrollArea->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    scrollArea->setMinimumSize(0, 0);
    scrollArea->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    return scrollArea;
}

void configureDock(QDockWidget *dock)
{
    dock->setAllowedAreas(Qt::LeftDockWidgetArea | Qt::RightDockWidgetArea | Qt::BottomDockWidgetArea);
    dock->setFeatures(
        QDockWidget::DockWidgetClosable
        | QDockWidget::DockWidgetMovable
        | QDockWidget::DockWidgetFloatable);
    dock->setMinimumSize(0, 0);
}

void configureTable(QTableWidget *table)
{
    table->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    table->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    table->setSizeAdjustPolicy(QAbstractScrollArea::AdjustIgnored);
}
}

void MainWindow::setupUi()
{
    setWindowTitle("AI NPC Debug Console");
    setDockOptions(
        QMainWindow::AllowNestedDocks
        | QMainWindow::AllowTabbedDocks
        | QMainWindow::AnimatedDocks);
    setTabPosition(Qt::AllDockWidgetAreas, QTabWidget::North);

    auto *root = new QWidget(this);
    auto *rootLayout = new QVBoxLayout(root);

    auto *topBar = new QGridLayout();
    baseUrlEdit_ = new QLineEdit("http://127.0.0.1:8000", root);
    playerIdEdit_ = new QLineEdit("player_001", root);
    npcCombo_ = new QComboBox(root);
    refreshButton_ = new QPushButton("Refresh", root);
    healthButton_ = new QPushButton("Health", root);
    cancelRequestsButton_ = new QPushButton("Cancel", root);
    requestStatusLabel_ = new QLabel("Idle", this);
    requestStatusLabel_->setMinimumWidth(0);
    requestStatusLabel_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
    baseUrlEdit_->setMinimumWidth(160);
    playerIdEdit_->setMinimumWidth(120);
    npcCombo_->setMinimumWidth(120);
    baseUrlEdit_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    playerIdEdit_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    npcCombo_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);

    auto *topButtons = new QHBoxLayout();
    topButtons->addStretch(1);
    topButtons->addWidget(refreshButton_);
    topButtons->addWidget(healthButton_);
    topButtons->addWidget(cancelRequestsButton_);

    topBar->addWidget(new QLabel("API", root), 0, 0);
    topBar->addWidget(baseUrlEdit_, 0, 1);
    topBar->addWidget(new QLabel("Player", root), 0, 2);
    topBar->addWidget(playerIdEdit_, 0, 3);
    topBar->addWidget(new QLabel("NPC", root), 0, 4);
    topBar->addWidget(npcCombo_, 0, 5);
    topBar->addLayout(topButtons, 1, 0, 1, 6);
    topBar->setColumnStretch(1, 4);
    topBar->setColumnStretch(3, 1);
    topBar->setColumnStretch(5, 1);
    rootLayout->addLayout(topBar);
    statusBar()->addPermanentWidget(requestStatusLabel_, 1);

    mainSplitter_ = new QSplitter(Qt::Horizontal, root);
    rootLayout->addWidget(mainSplitter_, 1);

    auto *leftPanel = new QWidget(mainSplitter_);
    auto *leftLayout = new QVBoxLayout(leftPanel);
    npcTable_ = new QTableWidget(leftPanel);
    npcTable_->setColumnCount(5);
    npcTable_->setHorizontalHeaderLabels({"ID", "Name", "Role", "Faction", "Location"});
    npcTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    configureTable(npcTable_);
    npcTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
    npcTable_->setSelectionMode(QAbstractItemView::SingleSelection);

    stateTree_ = new QTreeWidget(leftPanel);
    stateTree_->setHeaderLabels({"State", "Value"});
    stateTree_->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
    stateTree_->header()->setSectionResizeMode(1, QHeaderView::Stretch);
    stateTree_->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);

    summaryText_ = new QTextEdit(leftPanel);
    summaryText_->setReadOnly(true);
    summaryText_->setMinimumHeight(70);
    summaryText_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    leftLayout->addWidget(new QLabel("NPC Profiles", leftPanel));
    leftLayout->addWidget(npcTable_, 2);
    leftLayout->addWidget(new QLabel("Player State", leftPanel));
    leftLayout->addWidget(stateTree_, 3);
    leftLayout->addWidget(new QLabel("Summary Memory", leftPanel));
    leftLayout->addWidget(summaryText_, 1);

    auto *centerPanel = new QWidget(mainSplitter_);
    auto *centerLayout = new QVBoxLayout(centerPanel);
    chatView_ = new QTextEdit(centerPanel);
    chatView_->setReadOnly(true);

    auto *messageLayout = new QHBoxLayout();
    messageEdit_ = new QLineEdit(centerPanel);
    messageEdit_->setPlaceholderText("Message to selected NPC");
    sendButton_ = new QPushButton("Send", centerPanel);
    cancelChatButton_ = new QPushButton("Cancel", centerPanel);
    debugPromptButton_ = new QPushButton("Debug Prompt", centerPanel);
    clearHistoryButton_ = new QPushButton("Clear History", centerPanel);
    auto *messagePanelLayout = new QVBoxLayout();
    auto *messageActionLayout = new QHBoxLayout();
    messageLayout->addWidget(messageEdit_, 1);
    messageLayout->addWidget(sendButton_);
    messageActionLayout->addStretch(1);
    messageActionLayout->addWidget(cancelChatButton_);
    messageActionLayout->addWidget(debugPromptButton_);
    messageActionLayout->addWidget(clearHistoryButton_);
    messagePanelLayout->addLayout(messageLayout);
    messagePanelLayout->addLayout(messageActionLayout);

    centerLayout->addWidget(new QLabel("Conversation", centerPanel));
    centerLayout->addWidget(chatView_, 1);
    centerLayout->addLayout(messagePanelLayout);

    auto *contextTab = new QWidget();
    auto *contextLayout = new QVBoxLayout(contextTab);
    auto *tokenLayout = new QVBoxLayout();
    tokenUsageLabel_ = new QLabel("Context window: 0 / 0 tokens", contextTab);
    tokenUsageLabel_->setWordWrap(true);
    tokenUsageLabel_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Minimum);
    tokenUsageLabel_->setMinimumHeight(tokenUsageLabel_->fontMetrics().lineSpacing() + 6);
    tokenUsageBar_ = new QProgressBar(contextTab);
    tokenUsageBar_->setRange(0, 100);
    tokenUsageBar_->setValue(0);
    tokenBudgetChart_ = new TokenBudgetChart(contextTab);
    contextWindowLabel_ = new QLabel("Selected short-term: 0, long-term: 0, summary: false", contextTab);
    contextWindowLabel_->setWordWrap(true);
    contextWindowLabel_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Minimum);
    contextWindowLabel_->setMinimumHeight(contextWindowLabel_->fontMetrics().lineSpacing() * 2 + 6);
    tokenLayout->addWidget(tokenUsageLabel_);
    tokenLayout->addWidget(tokenBudgetChart_);
    tokenLayout->addWidget(tokenUsageBar_);
    tokenLayout->addWidget(contextWindowLabel_);

    contextTable_ = new QTableWidget(contextTab);
    contextTable_->setColumnCount(2);
    contextTable_->setHorizontalHeaderLabels({"Metric", "Value"});
    contextTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    configureTable(contextTable_);
    sectionTokenTable_ = new QTableWidget(contextTab);
    sectionTokenTable_->setColumnCount(2);
    sectionTokenTable_->setHorizontalHeaderLabels({"Section", "Tokens"});
    sectionTokenTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    configureTable(sectionTokenTable_);
    promptText_ = new QTextEdit(contextTab);
    promptText_->setReadOnly(true);
    contextLayout->addLayout(tokenLayout);
    contextLayout->addWidget(contextTable_, 1);
    contextLayout->addWidget(new QLabel("Section Tokens", contextTab));
    contextLayout->addWidget(sectionTokenTable_, 1);
    contextLayout->addWidget(new QLabel("Prompt", contextTab));
    contextLayout->addWidget(promptText_, 2);
    contextDock_ = new QDockWidget("Context", this);
    contextDock_->setObjectName("ContextDock");
    configureDock(contextDock_);
    contextDock_->setWidget(wrapDockPanel(contextTab, contextDock_));
    addDockWidget(Qt::RightDockWidgetArea, contextDock_);

    auto *actionsTab = new QWidget();
    auto *actionsLayout = new QVBoxLayout(actionsTab);
    actionTable_ = new QTableWidget(actionsTab);
    actionTable_->setColumnCount(5);
    actionTable_->setHorizontalHeaderLabels({"Kind", "Tool", "Success", "Status", "Message/Data"});
    actionTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    actionTable_->horizontalHeader()->setSectionResizeMode(4, QHeaderView::Stretch);
    configureTable(actionTable_);
    rawResponseText_ = new QTextEdit(actionsTab);
    rawResponseText_->setReadOnly(true);
    actionsLayout->addWidget(actionTable_, 2);
    actionsLayout->addWidget(new QLabel("Raw Response", actionsTab));
    actionsLayout->addWidget(rawResponseText_, 1);
    actionsDock_ = new QDockWidget("Actions", this);
    actionsDock_->setObjectName("ActionsDock");
    configureDock(actionsDock_);
    actionsDock_->setWidget(wrapDockPanel(actionsTab, actionsDock_));
    addDockWidget(Qt::RightDockWidgetArea, actionsDock_);
    tabifyDockWidget(contextDock_, actionsDock_);

    auto *questTab = new QWidget();
    auto *questLayout = new QVBoxLayout(questTab);
    auto *questControls = new QHBoxLayout();
    questRefreshButton_ = new QPushButton("Refresh", questTab);
    questControls->addStretch(1);
    questControls->addWidget(questRefreshButton_);

    questTable_ = new QTableWidget(questTab);
    questTable_->setColumnCount(6);
    questTable_->setHorizontalHeaderLabels({"Quest", "Status", "Objectives", "Completed", "Remaining", "Source"});
    questTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    questTable_->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    configureTable(questTable_);
    questTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
    questTable_->setSelectionMode(QAbstractItemView::SingleSelection);

    questObjectiveTable_ = new QTableWidget(questTab);
    questObjectiveTable_->setColumnCount(9);
    questObjectiveTable_->setHorizontalHeaderLabels(
        {"Quest", "Objective", "Status", "Type", "Item/Target", "NPC", "Location", "Quantity", "Description"});
    questObjectiveTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    questObjectiveTable_->horizontalHeader()->setSectionResizeMode(8, QHeaderView::Stretch);
    configureTable(questObjectiveTable_);

    questRawText_ = new QTextEdit(questTab);
    questRawText_->setReadOnly(true);
    questRawText_->setMinimumHeight(80);

    questLayout->addLayout(questControls);
    questLayout->addWidget(new QLabel("Quests", questTab));
    questLayout->addWidget(questTable_, 1);
    questLayout->addWidget(new QLabel("Objectives", questTab));
    questLayout->addWidget(questObjectiveTable_, 2);
    questLayout->addWidget(new QLabel("Raw Quest State", questTab));
    questLayout->addWidget(questRawText_, 1);
    questDock_ = new QDockWidget("Quest", this);
    questDock_->setObjectName("QuestDock");
    configureDock(questDock_);
    questDock_->setWidget(wrapDockPanel(questTab, questDock_));
    addDockWidget(Qt::RightDockWidgetArea, questDock_);
    tabifyDockWidget(contextDock_, questDock_);

    auto *worldActionTab = new QWidget();
    auto *worldActionLayout = new QVBoxLayout(worldActionTab);
    worldInteractionTextEdit_ = new QTextEdit(worldActionTab);
    worldInteractionTextEdit_->setMinimumHeight(76);
    worldInteractionTextEdit_->setPlaceholderText("Describe what the player does in the world");
    worldInteractionExecuteButton_ = new QPushButton("Apply Description", worldActionTab);
    auto *worldInteractionButtons = new QHBoxLayout();
    worldInteractionButtons->addStretch(1);
    worldInteractionButtons->addWidget(worldInteractionExecuteButton_);

    auto *worldActionForm = new QFormLayout();
    worldActionTypeCombo_ = new QComboBox(worldActionTab);
    worldActionTypeCombo_->addItems(worldActionTypes());
    worldActionTargetEdit_ = new QLineEdit(worldActionTab);
    worldActionTargetEdit_->setPlaceholderText("target_id / enemy_id / object_id");
    worldActionNpcEdit_ = new QLineEdit(worldActionTab);
    worldActionNpcEdit_->setPlaceholderText("npc_id");
    worldActionLocationEdit_ = new QLineEdit(worldActionTab);
    worldActionLocationEdit_->setPlaceholderText("location id or name");
    worldActionItemEdit_ = new QLineEdit(worldActionTab);
    worldActionItemEdit_->setPlaceholderText("item_id");
    worldActionQuantitySpin_ = new QSpinBox(worldActionTab);
    worldActionQuantitySpin_->setRange(1, 99);
    worldActionQuantitySpin_->setValue(1);
    worldActionFlagEdit_ = new QLineEdit(worldActionTab);
    worldActionFlagEdit_->setPlaceholderText("optional world flag");
    worldActionConsumeCheck_ = new QCheckBox("Consume item on use", worldActionTab);
    worldActionConsumeCheck_->setChecked(true);
    worldActionFlagValueCheck_ = new QCheckBox("Set flag true", worldActionTab);
    worldActionFlagValueCheck_->setChecked(true);
    worldActionNoteEdit_ = new QTextEdit(worldActionTab);
    worldActionNoteEdit_->setMinimumHeight(64);
    worldActionNoteEdit_->setPlaceholderText("Optional event note");
    worldActionExecuteButton_ = new QPushButton("Execute", worldActionTab);
    worldActionResultText_ = new QTextEdit(worldActionTab);
    worldActionResultText_->setReadOnly(true);
    worldActionResultText_->setMinimumHeight(120);

    auto *worldActionOptions = new QHBoxLayout();
    worldActionOptions->addWidget(worldActionConsumeCheck_);
    worldActionOptions->addWidget(worldActionFlagValueCheck_);
    worldActionOptions->addStretch(1);
    auto *worldActionButtons = new QHBoxLayout();
    worldActionButtons->addStretch(1);
    worldActionButtons->addWidget(worldActionExecuteButton_);

    worldActionForm->addRow("Action", worldActionTypeCombo_);
    worldActionForm->addRow("Target", worldActionTargetEdit_);
    worldActionForm->addRow("NPC", worldActionNpcEdit_);
    worldActionForm->addRow("Location", worldActionLocationEdit_);
    worldActionForm->addRow("Item", worldActionItemEdit_);
    worldActionForm->addRow("Quantity", worldActionQuantitySpin_);
    worldActionForm->addRow("Flag", worldActionFlagEdit_);
    worldActionForm->addRow("Options", worldActionOptions);
    worldActionForm->addRow("Note", worldActionNoteEdit_);
    worldActionLayout->addWidget(new QLabel("World Interaction", worldActionTab));
    worldActionLayout->addWidget(worldInteractionTextEdit_);
    worldActionLayout->addLayout(worldInteractionButtons);
    worldActionLayout->addWidget(new QLabel("World Action History", worldActionTab));
    worldActionLayout->addWidget(worldActionResultText_, 1);
    worldActionLayout->addWidget(new QLabel("Structured Debug Action", worldActionTab));
    worldActionLayout->addLayout(worldActionForm);
    worldActionLayout->addLayout(worldActionButtons);
    worldActionDock_ = new QDockWidget("World Action", this);
    worldActionDock_->setObjectName("WorldActionDock");
    configureDock(worldActionDock_);
    worldActionDock_->setWidget(wrapDockPanel(worldActionTab, worldActionDock_));
    addDockWidget(Qt::RightDockWidgetArea, worldActionDock_);
    tabifyDockWidget(contextDock_, worldActionDock_);

    auto *worldEventsTab = new QWidget();
    auto *worldEventsLayout = new QVBoxLayout(worldEventsTab);
    auto *worldEventsControls = new QHBoxLayout();
    worldEventsRefreshButton_ = new QPushButton("Refresh", worldEventsTab);
    worldEventsControls->addStretch(1);
    worldEventsControls->addWidget(worldEventsRefreshButton_);
    worldEventsTable_ = new QTableWidget(worldEventsTab);
    worldEventsTable_->setColumnCount(9);
    worldEventsTable_->setHorizontalHeaderLabels(
        {"Created", "Type", "Status", "Location", "Player", "Source NPC", "Subjects", "Confidence", "Text"});
    worldEventsTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    worldEventsTable_->horizontalHeader()->setSectionResizeMode(8, QHeaderView::Stretch);
    configureTable(worldEventsTable_);
    worldEventsRawText_ = new QTextEdit(worldEventsTab);
    worldEventsRawText_->setReadOnly(true);
    worldEventsRawText_->setMinimumHeight(80);
    worldEventsLayout->addLayout(worldEventsControls);
    worldEventsLayout->addWidget(worldEventsTable_, 2);
    worldEventsLayout->addWidget(new QLabel("Raw Events", worldEventsTab));
    worldEventsLayout->addWidget(worldEventsRawText_, 1);
    worldEventsDock_ = new QDockWidget("World Events", this);
    worldEventsDock_->setObjectName("WorldEventsDock");
    configureDock(worldEventsDock_);
    worldEventsDock_->setWidget(wrapDockPanel(worldEventsTab, worldEventsDock_));
    addDockWidget(Qt::RightDockWidgetArea, worldEventsDock_);
    tabifyDockWidget(contextDock_, worldEventsDock_);

    auto *memoryTab = new QWidget();
    auto *memoryLayout = new QVBoxLayout(memoryTab);
    auto *memoryControls = new QHBoxLayout();
    memoryTypeCombo_ = new QComboBox(memoryTab);
    memoryTypeCombo_->addItems(memoryTypes());
    memoryTypeCombo_->setToolTip("Memory type filter");
    memorySearchEdit_ = new QLineEdit(memoryTab);
    memorySearchEdit_->setPlaceholderText("search text");
    memoryRefreshButton_ = new QPushButton("List", memoryTab);
    memorySearchButton_ = new QPushButton("Search", memoryTab);
    memoryControls->addWidget(memoryTypeCombo_);
    memoryControls->addWidget(memorySearchEdit_, 1);
    memoryControls->addWidget(memoryRefreshButton_);
    memoryControls->addWidget(memorySearchButton_);

    auto *memoryEditorLayout = new QFormLayout();
    memoryIdEdit_ = new QLineEdit(memoryTab);
    memoryIdEdit_->setReadOnly(true);
    memoryEditTypeCombo_ = new QComboBox(memoryTab);
    memoryEditTypeCombo_->addItems(memoryTypes().mid(1));
    memoryEditTypeCombo_->setCurrentText("general");
    memoryTagsEdit_ = new QLineEdit(memoryTab);
    memoryTagsEdit_->setPlaceholderText("comma separated tags");
    memoryImportanceSpin_ = new QSpinBox(memoryTab);
    memoryImportanceSpin_->setRange(1, 10);
    memoryImportanceSpin_->setValue(5);
    memoryTextEdit_ = new QTextEdit(memoryTab);
    memoryTextEdit_->setMinimumHeight(70);
    memoryTextEdit_->setPlaceholderText("long-term memory text");
    memoryEditorLayout->addRow("ID", memoryIdEdit_);
    memoryEditorLayout->addRow("Type", memoryEditTypeCombo_);
    memoryEditorLayout->addRow("Importance", memoryImportanceSpin_);
    memoryEditorLayout->addRow("Tags", memoryTagsEdit_);
    memoryEditorLayout->addRow("Text", memoryTextEdit_);

    auto *memoryCrudLayout = new QHBoxLayout();
    memoryNewButton_ = new QPushButton("New", memoryTab);
    memoryCreateButton_ = new QPushButton("Create", memoryTab);
    memoryUpdateButton_ = new QPushButton("Update", memoryTab);
    memoryDeleteButton_ = new QPushButton("Delete", memoryTab);
    memoryCrudLayout->addStretch(1);
    memoryCrudLayout->addWidget(memoryNewButton_);
    memoryCrudLayout->addWidget(memoryCreateButton_);
    memoryCrudLayout->addWidget(memoryUpdateButton_);
    memoryCrudLayout->addWidget(memoryDeleteButton_);

    memoryTable_ = new QTableWidget(memoryTab);
    memoryTable_->setColumnCount(6);
    memoryTable_->setHorizontalHeaderLabels({"Type", "Importance", "Tags", "Created", "Text", "ID"});
    memoryTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    memoryTable_->horizontalHeader()->setSectionResizeMode(4, QHeaderView::Stretch);
    configureTable(memoryTable_);
    memoryTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
    memoryTable_->setSelectionMode(QAbstractItemView::SingleSelection);
    memoryTable_->setVisible(false);

    memoryList_ = new QListWidget(memoryTab);
    memoryList_->setItemDelegate(new MemoryCardDelegate(memoryList_));
    memoryList_->setSelectionMode(QAbstractItemView::SingleSelection);
    memoryList_->setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);
    memoryList_->setUniformItemSizes(false);
    memoryLayout->addLayout(memoryControls);
    memoryLayout->addWidget(memoryList_, 1);
    memoryLayout->addWidget(memoryTable_);
    memoryLayout->addLayout(memoryEditorLayout);
    memoryLayout->addLayout(memoryCrudLayout);
    memoryDock_ = new QDockWidget("Memory", this);
    memoryDock_->setObjectName("MemoryDock");
    configureDock(memoryDock_);
    memoryDock_->setWidget(wrapDockPanel(memoryTab, memoryDock_));
    addDockWidget(Qt::RightDockWidgetArea, memoryDock_);
    tabifyDockWidget(contextDock_, memoryDock_);

    auto *traceTab = new QWidget();
    auto *traceLayout = new QVBoxLayout(traceTab);
    traceTimeline_ = new TraceTimelineWidget(traceTab);
    traceTable_ = new QTableWidget(traceTab);
    traceTable_->setColumnCount(9);
    traceTable_->setHorizontalHeaderLabels({"Request", "Type", "NPC", "Player", "Tokens", "Actions", "Ms", "Error", "Message"});
    traceTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    traceTable_->horizontalHeader()->setSectionResizeMode(8, QHeaderView::Stretch);
    configureTable(traceTable_);
    traceTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
    traceTable_->setSelectionMode(QAbstractItemView::SingleSelection);
    traceRequestLabel_ = new QLabel("Selected trace: none", traceTab);
    traceRequestLabel_->setWordWrap(true);
    traceRequestLabel_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Minimum);
    traceMemoryText_ = new QTextEdit(traceTab);
    traceMemoryText_->setReadOnly(true);
    traceMemoryText_->setMinimumHeight(80);
    traceDetailText_ = new QTextEdit(traceTab);
    traceDetailText_->setReadOnly(true);
    traceLayout->addWidget(traceRequestLabel_);
    traceLayout->addWidget(traceTimeline_);
    traceLayout->addWidget(traceTable_, 1);
    traceLayout->addWidget(new QLabel("Trace Memory Hits", traceTab));
    traceLayout->addWidget(traceMemoryText_, 1);
    traceLayout->addWidget(new QLabel("Trace Detail", traceTab));
    traceLayout->addWidget(traceDetailText_, 2);
    traceDock_ = new QDockWidget("Trace", this);
    traceDock_->setObjectName("TraceDock");
    configureDock(traceDock_);
    traceDock_->setWidget(wrapDockPanel(traceTab, traceDock_));
    addDockWidget(Qt::RightDockWidgetArea, traceDock_);
    tabifyDockWidget(contextDock_, traceDock_);

    statusText_ = new QTextEdit(this);
    statusText_->setReadOnly(true);
    statusDock_ = new QDockWidget("Status", this);
    statusDock_->setObjectName("StatusDock");
    configureDock(statusDock_);
    statusDock_->setWidget(statusText_);
    addDockWidget(Qt::BottomDockWidgetArea, statusDock_);

    auto *viewMenu = menuBar()->addMenu("View");
    viewMenu->addAction(contextDock_->toggleViewAction());
    viewMenu->addAction(actionsDock_->toggleViewAction());
    viewMenu->addAction(questDock_->toggleViewAction());
    viewMenu->addAction(worldActionDock_->toggleViewAction());
    viewMenu->addAction(worldEventsDock_->toggleViewAction());
    viewMenu->addAction(memoryDock_->toggleViewAction());
    viewMenu->addAction(traceDock_->toggleViewAction());
    viewMenu->addAction(statusDock_->toggleViewAction());
    viewMenu->addSeparator();
    auto *resetLayoutAction = viewMenu->addAction("Reset Layout");
    connect(resetLayoutAction, &QAction::triggered, this, [this]() {
        resetLayoutToDefault();
    });

    mainSplitter_->addWidget(leftPanel);
    mainSplitter_->addWidget(centerPanel);
    mainSplitter_->setStretchFactor(0, 2);
    mainSplitter_->setStretchFactor(1, 3);

    setCentralWidget(root);
    applyDefaultDockLayout();
}

void MainWindow::connectSignals()
{
    connect(refreshButton_, &QPushButton::clicked, this, [this]() {
        refreshAll(true);
    });
    connect(healthButton_, &QPushButton::clicked, this, [this]() {
        applyBaseUrl();
        api_.fetchHealth();
    });
    connect(cancelRequestsButton_, &QPushButton::clicked, this, &MainWindow::cancelAllRequests);
    connect(baseUrlEdit_, &QLineEdit::editingFinished, this, [this]() {
        savePersistentSettings();
    });
    connect(playerIdEdit_, &QLineEdit::editingFinished, this, [this]() {
        savePersistentSettings();
    });
    connect(sendButton_, &QPushButton::clicked, this, &MainWindow::sendChat);
    connect(cancelChatButton_, &QPushButton::clicked, this, &MainWindow::cancelConversationRequest);
    connect(messageEdit_, &QLineEdit::returnPressed, this, &MainWindow::sendChat);
    connect(debugPromptButton_, &QPushButton::clicked, this, &MainWindow::requestDebugPrompt);
    connect(clearHistoryButton_, &QPushButton::clicked, this, &MainWindow::clearHistory);
    connect(questRefreshButton_, &QPushButton::clicked, this, [this]() {
        requestQuests(true);
    });
    connect(worldInteractionExecuteButton_, &QPushButton::clicked, this, &MainWindow::executeWorldInteraction);
    connect(worldActionTypeCombo_, &QComboBox::currentTextChanged, this, &MainWindow::updateWorldActionForm);
    connect(worldActionExecuteButton_, &QPushButton::clicked, this, &MainWindow::executeWorldAction);
    connect(worldEventsRefreshButton_, &QPushButton::clicked, this, [this]() {
        requestWorldEvents(true);
    });
    connect(memoryRefreshButton_, &QPushButton::clicked, this, [this]() {
        refreshMemory(true);
    });
    connect(memorySearchButton_, &QPushButton::clicked, this, [this]() {
        searchMemory(true);
    });
    connect(memoryTypeCombo_, &QComboBox::currentTextChanged, this, [this]() {
        savePersistentSettings();
        refreshMemory(true);
    });
    connect(memorySearchEdit_, &QLineEdit::editingFinished, this, [this]() {
        savePersistentSettings();
    });
    connect(memoryNewButton_, &QPushButton::clicked, this, [this]() {
        memoryTable_->clearSelection();
        memoryList_->clearSelection();
        memoryIdEdit_->clear();
        memoryEditTypeCombo_->setCurrentText(memoryTypeCombo_->currentText().trimmed().isEmpty()
            ? QString("general")
            : memoryTypeCombo_->currentText().trimmed());
        memoryImportanceSpin_->setValue(5);
        memoryTagsEdit_->clear();
        memoryTextEdit_->clear();
    });
    connect(memoryCreateButton_, &QPushButton::clicked, this, &MainWindow::createMemory);
    connect(memoryUpdateButton_, &QPushButton::clicked, this, &MainWindow::updateMemory);
    connect(memoryDeleteButton_, &QPushButton::clicked, this, &MainWindow::deleteMemory);
    connect(memoryTable_, &QTableWidget::itemSelectionChanged, this, &MainWindow::populateMemoryEditorFromSelection);
    connect(memoryList_, &QListWidget::itemClicked, this, &MainWindow::populateMemoryEditorFromCard);
    connect(npcCombo_, &QComboBox::currentTextChanged, this, [this]() {
        savePersistentSettings();
        refreshNpcScoped();
    });
    connect(mainSplitter_, &QSplitter::splitterMoved, this, [this]() {
        savePersistentSettings();
    });
    connect(npcTable_, &QTableWidget::cellDoubleClicked, this, [this](int row, int) {
        const QString npcId = npcTable_->item(row, 0)->text();
        const int index = npcCombo_->findData(npcId);
        if (index >= 0) {
            npcCombo_->setCurrentIndex(index);
        }
    });
    connect(traceTable_, &QTableWidget::cellDoubleClicked, this, [this](int row, int) {
        if (auto *requestItem = traceTable_->item(row, 0)) {
            fetchTraceDetail(requestItem->text());
        }
    });
    connect(traceTable_, &QTableWidget::itemSelectionChanged, this, &MainWindow::requestSelectedTrace);
    connect(traceTimeline_, &TraceTimelineWidget::traceSelected, this, [this](const QString &requestId) {
        fetchTraceDetail(requestId);
    });

    connect(&api_, &ApiClient::requestStarted, &requestTracker_, &AsyncRequestTracker::begin);
    connect(&api_, &ApiClient::requestFinished, &requestTracker_, &AsyncRequestTracker::finish);
    connect(&requestTracker_, &AsyncRequestTracker::stateChanged, this, &MainWindow::updateRequestControls);
    connect(&api_, &ApiClient::requestCancelled, this, &MainWindow::onRequestCancelled);

    connect(&api_, &ApiClient::healthLoaded, this, [this](const QJsonObject &health) {
        appendStatus("health: " + formatJsonObject(health));
    });
    connect(&api_, &ApiClient::npcsLoaded, this, &MainWindow::onNpcsLoaded);
    connect(&api_, &ApiClient::gameStateLoaded, this, &MainWindow::onGameStateLoaded);
    connect(&api_, &ApiClient::chatHistoryLoaded, this, &MainWindow::onChatHistoryLoaded);
    connect(&api_, &ApiClient::chatLoaded, this, &MainWindow::onChatLoaded);
    connect(&api_, &ApiClient::chatStreamStarted, this, &MainWindow::onChatStreamStarted);
    connect(&api_, &ApiClient::chatStreamDelta, this, &MainWindow::onChatStreamDelta);
    connect(&api_, &ApiClient::debugPromptLoaded, this, &MainWindow::onDebugPromptLoaded);
    connect(&api_, &ApiClient::longTermMemoriesLoaded, this, &MainWindow::onLongTermMemoriesLoaded);
    connect(&api_, &ApiClient::longTermSearchLoaded, this, &MainWindow::onLongTermSearchLoaded);
    connect(&api_, &ApiClient::longTermMemorySaved, this, [this](const QJsonObject &memory) {
        appendStatus("memory saved: " + memory.value("memory_id").toString());
        memoryIdEdit_->setText(memory.value("memory_id").toString());
        invalidateMemoryCache();
        refreshMemory(true);
    });
    connect(&api_, &ApiClient::longTermMemoryDeleted, this, [this](const QString &memoryId) {
        appendStatus("memory deleted: " + memoryId);
        memoryIdEdit_->clear();
        memoryTextEdit_->clear();
        invalidateMemoryCache();
        refreshMemory(true);
    });
    connect(&api_, &ApiClient::summaryLoaded, this, &MainWindow::onSummaryLoaded);
    connect(&api_, &ApiClient::questsLoaded, this, &MainWindow::onQuestsLoaded);
    connect(&api_, &ApiClient::worldInteractionApplied, this, &MainWindow::onWorldInteractionApplied);
    connect(&api_, &ApiClient::worldActionApplied, this, &MainWindow::onWorldActionApplied);
    connect(&api_, &ApiClient::worldEventsLoaded, this, &MainWindow::onWorldEventsLoaded);
    connect(&api_, &ApiClient::tracesLoaded, this, &MainWindow::onTracesLoaded);
    connect(&api_, &ApiClient::traceLoaded, this, &MainWindow::onTraceLoaded);
    connect(&api_, &ApiClient::apiError, this, &MainWindow::onApiError);

    updateWorldActionForm();
}

