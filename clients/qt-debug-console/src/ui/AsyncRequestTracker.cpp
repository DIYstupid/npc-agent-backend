#include "AsyncRequestTracker.h"

#include <algorithm>

#include <QStringList>

AsyncRequestTracker::AsyncRequestTracker(QObject *parent)
    : QObject(parent)
{
}

bool AsyncRequestTracker::isBusy() const
{
    return activeCount_ > 0;
}

bool AsyncRequestTracker::isBusy(const QString &operation) const
{
    return activeOperations_.value(operation, 0) > 0;
}

QString AsyncRequestTracker::statusText() const
{
    if (!isBusy()) {
        return lastResultText_.isEmpty() ? QString("Idle") : QString("Idle - %1").arg(lastResultText_);
    }

    QStringList operations = activeOperations_.keys();
    std::sort(operations.begin(), operations.end());

    QStringList labels;
    labels.reserve(operations.size());
    for (const QString &operation : operations) {
        const int count = activeOperations_.value(operation, 0);
        if (count <= 0) {
            continue;
        }

        labels.append(count == 1
            ? operation
            : QString("%1 x%2").arg(operation).arg(count));
    }

    return QString("Loading: %1").arg(labels.join(", "));
}

void AsyncRequestTracker::begin(const QString &operation)
{
    const bool wasBusy = isBusy();
    const int previousOperationCount = activeOperations_.value(operation, 0);

    activeOperations_.insert(operation, previousOperationCount + 1);
    ++activeCount_;

    if (!wasBusy) {
        emit busyChanged(true);
    }
    if (previousOperationCount == 0) {
        emit operationBusyChanged(operation, true);
    }
    emit stateChanged();
}

void AsyncRequestTracker::finish(const QString &operation, bool success, int statusCode)
{
    const bool wasBusy = isBusy();
    const int previousOperationCount = activeOperations_.value(operation, 0);
    if (previousOperationCount <= 0) {
        return;
    }

    if (previousOperationCount == 1) {
        activeOperations_.remove(operation);
        emit operationBusyChanged(operation, false);
    } else {
        activeOperations_.insert(operation, previousOperationCount - 1);
    }

    --activeCount_;
    if (activeCount_ < 0) {
        activeCount_ = 0;
    }

    lastResultText_ = success
        ? QString("%1 ok").arg(operation)
        : QString("%1 failed (%2)").arg(operation).arg(statusCode);

    if (wasBusy && !isBusy()) {
        emit busyChanged(false);
    }
    emit stateChanged();
}
