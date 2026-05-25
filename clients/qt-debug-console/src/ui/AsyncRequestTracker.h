#pragma once

#include <QHash>
#include <QObject>
#include <QString>

class AsyncRequestTracker : public QObject
{
    Q_OBJECT

public:
    explicit AsyncRequestTracker(QObject *parent = nullptr);

    bool isBusy() const;
    bool isBusy(const QString &operation) const;
    QString statusText() const;

public slots:
    void begin(const QString &operation);
    void finish(const QString &operation, bool success, int statusCode);

signals:
    void stateChanged();
    void busyChanged(bool busy);
    void operationBusyChanged(const QString &operation, bool busy);

private:
    int activeCount_ = 0;
    QHash<QString, int> activeOperations_;
    QString lastResultText_;
};
