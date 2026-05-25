cmake_minimum_required(VERSION 3.16)

project(NpcAgentDebugConsole LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

option(BUILD_QT_CLIENT_TESTS "Build Qt debug console unit tests" OFF)

find_package(QT NAMES Qt6 Qt5 REQUIRED COMPONENTS Core Widgets Network)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Widgets Network)

set(NPC_AGENT_DEBUG_CONSOLE_SOURCES
    src/api/ApiClient.cpp
    src/api/ApiClient.h
    src/api/SseEventParser.cpp
    src/api/SseEventParser.h
    src/common/JsonUtils.cpp
    src/common/JsonUtils.h
    src/ui/AsyncRequestTracker.cpp
    src/ui/AsyncRequestTracker.h
    src/ui/ClientCache.cpp
    src/ui/ClientCache.h
    src/ui/ClientSettings.cpp
    src/ui/ClientSettings.h
    src/ui/MainWindow.cpp
    src/ui/MainWindow.h
    src/ui/MainWindowActions.cpp
    src/ui/MainWindowRender.cpp
    src/ui/MainWindowRequestState.cpp
    src/ui/MainWindowUi.cpp
    src/ui/widgets/MemoryCardDelegate.cpp
    src/ui/widgets/MemoryCardDelegate.h
    src/ui/widgets/TraceTimelineWidget.cpp
    src/ui/widgets/TraceTimelineWidget.h
    src/ui/widgets/TokenBudgetChart.cpp
    src/ui/widgets/TokenBudgetChart.h
    resources/resources.qrc
)

add_executable(NpcAgentDebugConsole
    src/main.cpp
    ${NPC_AGENT_DEBUG_CONSOLE_SOURCES}
)

target_include_directories(NpcAgentDebugConsole
    PRIVATE
        src
)

target_link_libraries(NpcAgentDebugConsole
    PRIVATE
        Qt${QT_VERSION_MAJOR}::Core
        Qt${QT_VERSION_MAJOR}::Widgets
        Qt${QT_VERSION_MAJOR}::Network
)

if(BUILD_QT_CLIENT_TESTS)
    enable_testing()
    find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Test)

    add_executable(ClientSettingsTests
        tests/TestClientSettings.cpp
        src/ui/ClientSettings.cpp
        src/ui/ClientSettings.h
    )
    target_include_directories(ClientSettingsTests PRIVATE src)
    target_link_libraries(ClientSettingsTests
        PRIVATE
            Qt${QT_VERSION_MAJOR}::Core
            Qt${QT_VERSION_MAJOR}::Test
    )
    add_test(NAME ClientSettingsTests COMMAND ClientSettingsTests)

    add_executable(ClientCacheTests
        tests/TestClientCache.cpp
        src/ui/ClientCache.cpp
        src/ui/ClientCache.h
    )
    target_include_directories(ClientCacheTests PRIVATE src)
    target_link_libraries(ClientCacheTests
        PRIVATE
            Qt${QT_VERSION_MAJOR}::Core
            Qt${QT_VERSION_MAJOR}::Test
    )
    add_test(NAME ClientCacheTests COMMAND ClientCacheTests)

    add_executable(AsyncRequestTrackerTests
        tests/TestAsyncRequestTracker.cpp
        src/ui/AsyncRequestTracker.cpp
        src/ui/AsyncRequestTracker.h
    )
    target_include_directories(AsyncRequestTrackerTests PRIVATE src)
    target_link_libraries(AsyncRequestTrackerTests
        PRIVATE
            Qt${QT_VERSION_MAJOR}::Core
            Qt${QT_VERSION_MAJOR}::Test
    )
    add_test(NAME AsyncRequestTrackerTests COMMAND AsyncRequestTrackerTests)

    add_executable(SseEventParserTests
        tests/TestSseEventParser.cpp
        src/api/SseEventParser.cpp
        src/api/SseEventParser.h
    )
    target_include_directories(SseEventParserTests PRIVATE src)
    target_link_libraries(SseEventParserTests
        PRIVATE
            Qt${QT_VERSION_MAJOR}::Core
            Qt${QT_VERSION_MAJOR}::Test
    )
    add_test(NAME SseEventParserTests COMMAND SseEventParserTests)
endif()
