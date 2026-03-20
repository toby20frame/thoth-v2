"""
Sends reports to Discord using the existing bot token.
Posts to the commands channel.
"""
import httpx
from models import DailyReport
from config import DISCORD_CHANNELS
from pathlib import Path


def _get_token() -> str:
    token_path = Path.home() / ".openclaw" / "credentials" / "discord.token"
    return token_path.read_text().strip()


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
    if report.needs_human:
        lines.append("\n🙋 **Needs You**")
        for item in report.needs_human[:3]:
            lines.append(f"  • {item}")
    if report.research_prompts:
        lines.append("\n🔬 **Research Prompts**")
        for p in report.research_prompts[:3]:
            lines.append(f"  • {p[:100]}")
    return "\n".join(lines)


def send_report(report: DailyReport):
    """Send report to Discord commands channel via bot token."""
    text = format_report_text(report)
    
    # Print locally too
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60 + "\n")
    
    # Send to Discord
    try:
        token = _get_token()
        channel_id = DISCORD_CHANNELS["commands"]
        resp = httpx.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json={"content": text},
            timeout=10,
        )
        if resp.status_code == 200:
            print("Report sent to Discord ✓")
        else:
            print(f"Discord send failed: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"Discord send error: {e}")
