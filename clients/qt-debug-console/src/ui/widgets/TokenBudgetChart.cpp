#include "TokenBudgetChart.h"

#include <QFontMetrics>
#include <QJsonObject>
#include <QPainter>
#include <QPaintEvent>
#include <QSizePolicy>
#include <QStringList>
#include <QtGlobal>

TokenBudgetChart::TokenBudgetChart(QWidget *parent)
    : QWidget(parent)
{
    setMinimumHeight(112);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
}

void TokenBudgetChart::setReport(const QJsonObject &report)
{
    tokenBudget_ = report.value("token_budget").toInt();
    estimatedPromptTokens_ = report.value("estimated_prompt_tokens").toInt();
    sections_.clear();

    const QJsonObject sectionTokens = report.value("section_tokens").toObject();
    for (auto it = sectionTokens.constBegin(); it != sectionTokens.constEnd(); ++it) {
        const int tokens = it.value().toInt();
        if (tokens <= 0 || it.key() == "full_prompt") {
            continue;
        }

        sections_.append(Section{it.key(), tokens});
    }

    updateGeometry();
    update();
}

void TokenBudgetChart::paintEvent(QPaintEvent *)
{
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);

    const QRect outer = rect().adjusted(8, 8, -8, -8);
    painter.setPen(QColor("#303941"));
    painter.setBrush(QColor("#0f1316"));
    painter.drawRoundedRect(outer, 6, 6);

    const QRect bar = QRect(outer.left() + 12, outer.top() + 14, outer.width() - 24, 18);
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor("#1b2228"));
    painter.drawRoundedRect(bar, 4, 4);

    const int denominator = qMax(1, tokenBudget_);
    int x = bar.left();
    for (int index = 0; index < sections_.size(); ++index) {
        const Section &section = sections_.at(index);
        const int width = qMax(2, qRound((section.tokens * 1.0 / denominator) * bar.width()));
        const QRect segment(x, bar.top(), qMin(width, bar.right() - x + 1), bar.height());
        if (segment.width() > 0) {
            painter.setBrush(colorForIndex(index));
            painter.drawRoundedRect(segment, 3, 3);
        }
        x += width;
        if (x >= bar.right()) {
            break;
        }
    }

    painter.setPen(QColor("#d9dee3"));
    const int percent = tokenBudget_ > 0 ? qMin(100, qRound((estimatedPromptTokens_ * 100.0) / tokenBudget_)) : 0;
    const QRect usageTextRect(outer.left() + 12, bar.bottom() + 8, outer.width() - 24, 18);
    painter.drawText(
        usageTextRect,
        Qt::AlignLeft | Qt::AlignVCenter,
        QString("Prompt %1 / %2 tokens (%3%)").arg(estimatedPromptTokens_).arg(tokenBudget_).arg(percent));

    QStringList legend;
    for (int index = 0; index < qMin(4, sections_.size()); ++index) {
        const Section &section = sections_.at(index);
        legend.append(QString("%1 %2").arg(section.name).arg(section.tokens));
    }
    painter.setPen(QColor("#9ba7b1"));
    const QRect legendRect(outer.left() + 12, usageTextRect.bottom() + 6, outer.width() - 24, 18);
    painter.drawText(
        legendRect,
        Qt::AlignLeft | Qt::AlignVCenter,
        painter.fontMetrics().elidedText(legend.join("   "), Qt::ElideRight, legendRect.width()));
}

QSize TokenBudgetChart::minimumSizeHint() const
{
    return QSize(260, 112);
}

QColor TokenBudgetChart::colorForIndex(int index) const
{
    static const QList<QColor> colors{
        QColor("#4f8fdb"),
        QColor("#58a36b"),
        QColor("#d6a44f"),
        QColor("#b86fb4"),
        QColor("#5aa6a6"),
        QColor("#c06c5b"),
    };
    return colors.at(index % colors.size());
}
