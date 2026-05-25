#pragma once

#include <QColor>
#include <QJsonObject>
#include <QList>
#include <QSize>
#include <QString>
#include <QWidget>

class TokenBudgetChart : public QWidget
{
    Q_OBJECT

public:
    explicit TokenBudgetChart(QWidget *parent = nullptr);

    void setReport(const QJsonObject &report);

protected:
    void paintEvent(QPaintEvent *event) override;
    QSize minimumSizeHint() const override;

private:
    struct Section
    {
        QString name;
        int tokens = 0;
    };

    QColor colorForIndex(int index) const;

    int tokenBudget_ = 0;
    int estimatedPromptTokens_ = 0;
    QList<Section> sections_;
};
