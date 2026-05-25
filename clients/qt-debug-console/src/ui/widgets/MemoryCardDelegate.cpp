#include "MemoryCardDelegate.h"

#include <QAbstractItemView>
#include <QPainter>
#include <QStyle>
#include <QStyleOptionViewItem>
#include <QtGlobal>

namespace {
constexpr int TypeRole = Qt::UserRole + 1;
constexpr int ImportanceRole = Qt::UserRole + 2;
constexpr int TagsRole = Qt::UserRole + 3;
constexpr int TextRole = Qt::UserRole + 4;
constexpr int CreatedRole = Qt::UserRole + 5;
}

MemoryCardDelegate::MemoryCardDelegate(QObject *parent)
    : QStyledItemDelegate(parent)
{
}

void MemoryCardDelegate::paint(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const
{
    painter->save();
    painter->setRenderHint(QPainter::Antialiasing, true);

    const QRect card = option.rect.adjusted(6, 5, -6, -5);
    const bool selected = option.state & QStyle::State_Selected;
    const int importance = index.data(ImportanceRole).toInt();

    painter->setPen(QPen(selected ? QColor("#6ca6c8") : QColor("#303941"), 1));
    painter->setBrush(selected ? QColor("#1d3441") : QColor("#151b20"));
    painter->drawRoundedRect(card, 6, 6);

    const QRect stripe(card.left(), card.top(), 5, card.height());
    painter->fillRect(stripe, importanceColor(importance));

    const QString type = index.data(TypeRole).toString();
    const QString tags = index.data(TagsRole).toString();
    const QString text = index.data(TextRole).toString();
    const QString created = index.data(CreatedRole).toString();

    QRect inner = card.adjusted(14, 10, -12, -10);
    painter->setPen(Qt::NoPen);
    painter->setBrush(QColor("#26313a"));
    const QRect badge(inner.left(), inner.top(), qMin(120, 48 + type.size() * 7), 22);
    painter->drawRoundedRect(badge, 4, 4);
    painter->setPen(QColor("#e4e9ee"));
    painter->drawText(badge.adjusted(8, 0, -8, 0), Qt::AlignVCenter | Qt::AlignLeft, type);

    painter->setPen(QColor("#9ba7b1"));
    painter->drawText(
        QRect(badge.right() + 10, inner.top(), inner.width() - badge.width() - 10, 22),
        Qt::AlignVCenter | Qt::AlignRight,
        QString("importance %1  %2").arg(importance).arg(created));

    QRect textRect(inner.left(), inner.top() + 30, inner.width(), 42);
    painter->setPen(QColor("#d9dee3"));
    painter->drawText(textRect, Qt::TextWordWrap, option.fontMetrics.elidedText(text.simplified(), Qt::ElideRight, textRect.width() * 2));

    if (!tags.isEmpty()) {
        painter->setPen(QColor("#8db3c7"));
        painter->drawText(QRect(inner.left(), inner.bottom() - 20, inner.width(), 18), Qt::AlignLeft | Qt::AlignVCenter, tags);
    }

    painter->restore();
}

QSize MemoryCardDelegate::sizeHint(const QStyleOptionViewItem &, const QModelIndex &) const
{
    return QSize(220, 100);
}

QColor MemoryCardDelegate::importanceColor(int importance) const
{
    if (importance >= 8) {
        return QColor("#d65f5f");
    }
    if (importance >= 5) {
        return QColor("#d6a44f");
    }
    return QColor("#4f8fdb");
}
