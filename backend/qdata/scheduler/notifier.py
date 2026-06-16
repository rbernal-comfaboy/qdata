import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from qdata.core.config import settings

logger = logging.getLogger(__name__)

try:
    import aiosmtplib
    HAS_SMTP = True
except ImportError:
    HAS_SMTP = False


async def send_email(
    to_emails: list[str],
    subject: str,
    html_body: str,
    text_body: str = "",
    attachment_path: str | None = None,
) -> bool:
    if not HAS_SMTP:
        logger.warning("aiosmtplib not installed, skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if attachment_path:
        from email.mime.base import MIMEBase
        from email import encoders
        try:
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={attachment_path.split('/')[-1]}")
                msg.attach(part)
        except Exception as e:
            logger.error(f"Failed to attach file: {e}")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_pass or None,
            start_tls=settings.smtp_port == 587,
        )
        logger.info(f"Email sent to {to_emails}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False



async def send_quality_report(
    to_emails: list[str],
    task_name: str,
    score: int,
    label: str,
    summary: str,
    report_path: str | None = None,
) -> bool:
    subject = f"QData - Reporte de Calidad: {task_name}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;background:#f4f4f4;padding:2rem">
<div style="max-width:600px;margin:auto;background:white;border-radius:12px;padding:2rem;
  box-shadow:0 4px 12px rgba(0,0,0,0.1)">
  <h1 style="color:#6366F1;margin:0">QData</h1>
  <p style="color:#666">Reporte: <strong>{task_name}</strong></p>
  <div style="text-align:center;padding:1.5rem">
    <div style="font-size:4rem;font-weight:bold;color:#333">{score}</div>
    <div style="font-size:1.2rem;color:#666;text-transform:uppercase">{label}</div>
  </div>
  <p style="color:#555">{summary}</p>
  <hr style="border:none;border-top:1px solid #eee">
  <p style="color:#999;font-size:0.8rem">Generado por QData</p>
</div></body></html>"""
    text = f"QData - Reporte: {task_name}\nScore: {score}/100 ({label})\n{summary}"

    return await send_email(to_emails, subject, html, text, report_path)
