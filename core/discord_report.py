from models import DailyReport


def format_report_text(report: DailyReport) -> str:
    lines = [f"**{report.status_line}**\n"]

    if report.metrics:
        lines.append("📊 **Metrics**")
        for k, v in report.metrics.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    if report.completed_tasks:
        lines.append(f"✅ **Completed** ({len(report.completed_tasks)})")
        for t in report.completed_tasks[:5]:
            lines.append(f"  • {t[:100]}")
        lines.append("")

    if report.failed_tasks:
        lines.append(f"❌ **Failed** ({len(report.failed_tasks)})")
        for t in report.failed_tasks[:5]:
            lines.append(f"  • {t[:100]}")

    return "\n".join(lines)


def send_report(report: DailyReport):
    text = format_report_text(report)
    print(text)

