#pragma once

#include <QColor>
#include <QJsonArray>
#include <QList>
#include <QRect>
#include <QSize>
#include <QString>
#include <QWidget>

class TraceTimelineWidget : public QWidget
{
    Q_OBJECT

public:
    explicit TraceTimelineWidget(QWidget *parent = nullptr);

    void setTraces(const QJsonArray &traces);
    void setActiveRequestId(const QString &requestId);
    QString activeRequestId() const;

signals:
    void traceSelected(const QString &requestId);

protected:
    void paintEvent(QPaintEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    QSize minimumSizeHint() const override;

private:
    struct TracePoint
    {
        QString requestId;
        QString agentType;
        QString playerId;
        QString preview;
        int elapsedMs = 0;
        int actionsCount = 0;
        int executedActionsCount = 0;
        bool hasError = false;
    };

    QRect pointRect(int index) const;
    QColor colorForPoint(const TracePoint &point) const;
    QString labelForPoint(const TracePoint &point) const;

    QList<TracePoint> traces_;
    QString activeRequestId_;
};
