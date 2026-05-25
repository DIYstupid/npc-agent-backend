#include "TraceTimelineWidget.h"

#include <QJsonObject>
#include <QMouseEvent>
#include <QPainter>
#include <QPaintEvent>
#include <QSizePolicy>
#include <QToolTip>
#include <QtGlobal>

namespace {
constexpr int PointDiameter = 16;
constexpr int HorizontalPadding = 24;
constexpr int LabelHeight = 18;
}

TraceTimelineWidget::TraceTimelineWidget(QWidget *parent)
    : QWidget(parent)
{
    setMouseTracking(true);
    setMinimumHeight(88);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
}

void TraceTimelineWidget::setTraces(const QJsonArray &traces)
{
    traces_.clear();
    traces_.reserve(traces.size());

    for (const QJsonValue &value : traces) {
        const QJsonObject trace = value.toObject();
        TracePoint point;
        point.requestId = trace.value("request_id").toString();
        point.agentType = trace.value("agent_type").toString("chat");
        point.playerId = trace.value("player_id").toString();
        point.preview = trace.value("message_preview").toString();
        point.elapsedMs = trace.value("elapsed_ms").toInt();
        point.actionsCount = trace.value("actions_count").toInt();
        point.executedActionsCount = trace.value("executed_actions_count").toInt();
        point.hasError = !trace.value("error").toString().isEmpty();
        if (!point.requestId.isEmpty()) {
            traces_.append(point);
        }
    }

    updateGeometry();
    update();
}

void TraceTimelineWidget::setActiveRequestId(const QString &requestId)
{
    if (activeRequestId_ == requestId) {
        return;
    }

    activeRequestId_ = requestId;
    update();
}

QString TraceTimelineWidget::activeRequestId() const
{
    return activeRequestId_;
}

void TraceTimelineWidget::paintEvent(QPaintEvent *)
{
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);

    const QRect content = rect().adjusted(12, 10, -12, -10);
    painter.fillRect(content, QColor("#0f1316"));

    if (traces_.isEmpty()) {
        painter.setPen(QColor("#7e8a94"));
        painter.drawText(content, Qt::AlignCenter, "No traces");
        return;
    }

    const int y = content.center().y() - 8;
    painter.setPen(QPen(QColor("#34404a"), 2));
    painter.drawLine(content.left() + HorizontalPadding, y, content.right() - HorizontalPadding, y);

    for (int index = 0; index < traces_.size(); ++index) {
        const TracePoint &point = traces_.at(index);
        const QRect marker = pointRect(index);
        const bool active = point.requestId == activeRequestId_;
        const QColor color = colorForPoint(point);

        painter.setPen(QPen(active ? QColor("#f0c85a") : QColor("#11161a"), active ? 3 : 1));
        painter.setBrush(color);
        painter.drawEllipse(marker);

        if (active) {
            painter.setPen(QPen(QColor("#f0c85a"), 1));
            painter.setBrush(Qt::NoBrush);
            painter.drawEllipse(marker.adjusted(-5, -5, 5, 5));
        }

        painter.setPen(QColor("#aeb8c2"));
        const QRect labelRect(marker.center().x() - 46, marker.bottom() + 6, 92, LabelHeight);
        painter.drawText(labelRect, Qt::AlignCenter, labelForPoint(point));
    }
}

void TraceTimelineWidget::mousePressEvent(QMouseEvent *event)
{
    for (int index = 0; index < traces_.size(); ++index) {
        const QRect marker = pointRect(index).adjusted(-8, -8, 8, 8);
        if (!marker.contains(event->pos())) {
            continue;
        }

        const TracePoint &point = traces_.at(index);
        setActiveRequestId(point.requestId);
        QToolTip::showText(
            event->globalPos(),
            QString("%1\n%2\n%3 ms, actions %4/%5")
                .arg(point.requestId, point.preview)
                .arg(point.elapsedMs)
                .arg(point.actionsCount)
                .arg(point.executedActionsCount),
            this);
        emit traceSelected(point.requestId);
        return;
    }

    QWidget::mousePressEvent(event);
}

QSize TraceTimelineWidget::minimumSizeHint() const
{
    return QSize(260, 88);
}

QRect TraceTimelineWidget::pointRect(int index) const
{
    const QRect content = rect().adjusted(12, 10, -12, -10);
    const int count = qMax(1, traces_.size());
    const int left = content.left() + HorizontalPadding;
    const int right = content.right() - HorizontalPadding;
    const int span = qMax(1, right - left);
    const int x = count == 1 ? content.center().x() : left + (span * index) / (count - 1);
    const int y = content.center().y() - 8;
    return QRect(x - PointDiameter / 2, y - PointDiameter / 2, PointDiameter, PointDiameter);
}

QColor TraceTimelineWidget::colorForPoint(const TracePoint &point) const
{
    if (point.hasError) {
        return QColor("#b84d4d");
    }
    if (point.agentType == "quest_agent") {
        return QColor("#4f8fdb");
    }
    if (point.agentType == "world_agent") {
        return QColor("#58a36b");
    }
    if (point.agentType == "world_action") {
        return QColor("#d69b42");
    }
    if (point.executedActionsCount > 0) {
        return QColor("#d69b42");
    }
    return QColor("#6f7f8f");
}

QString TraceTimelineWidget::labelForPoint(const TracePoint &point) const
{
    if (point.agentType == "quest_agent") {
        return "Quest";
    }
    if (point.agentType == "world_agent") {
        return "World";
    }
    if (point.agentType == "world_action") {
        return "Action";
    }
    return point.executedActionsCount > 0 ? "Action" : "Chat";
}
