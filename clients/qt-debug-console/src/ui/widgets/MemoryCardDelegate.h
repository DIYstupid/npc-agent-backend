#pragma once

#include <QColor>
#include <QSize>
#include <QStyledItemDelegate>

class QModelIndex;
class QPainter;
class QStyleOptionViewItem;

class MemoryCardDelegate : public QStyledItemDelegate
{
    Q_OBJECT

public:
    explicit MemoryCardDelegate(QObject *parent = nullptr);

    void paint(QPainter *painter, const QStyleOptionViewItem &option, const QModelIndex &index) const override;
    QSize sizeHint(const QStyleOptionViewItem &option, const QModelIndex &index) const override;

private:
    QColor importanceColor(int importance) const;
};
