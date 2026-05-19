import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "Javelaud <onboarding@resend.dev>")
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")


def _send_email(to: str, subject: str, html_body: str) -> None:
    if not resend.api_key:
        print(f"[EMAIL] (RESEND_API_KEY non configuré) À: {to} | Sujet: {subject}")
        return

    params = {
        "from": RESEND_FROM,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }
    response = resend.Emails.send(params)
    print(f"[EMAIL] Envoyé à {to} | id={response.get('id', '?')}")


def send_invitation_email(to_email: str, prenom: str, token: str) -> None:
    activation_url = f"{APP_URL}/invitation/{token}"
    subject = "Javelaud — Création de votre SASU : activez votre espace"
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
      <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div style="text-align: center; margin-bottom: 30px;">
          <h1 style="color: #0f1f45; font-size: 24px;">Javelaud</h1>
          <p style="color: #6b7280; font-size: 14px;">Cabinet juridique</p>
        </div>
        <h2 style="color: #1e3a8a;">Bonjour {prenom},</h2>
        <p style="color: #374151; line-height: 1.6;">
          Votre expert juridique Javelaud a ouvert un dossier pour la création de votre SASU.
          Cliquez sur le bouton ci-dessous pour activer votre espace personnel et compléter votre formulaire.
        </p>
        <div style="text-align: center; margin: 30px 0;">
          <a href="{activation_url}"
             style="background: linear-gradient(135deg, #1e3a8a, #4f46e5); color: white;
                    padding: 14px 32px; border-radius: 8px; text-decoration: none;
                    font-weight: bold; font-size: 16px;">
            Activer mon espace →
          </a>
        </div>
        <p style="color: #6b7280; font-size: 13px;">
          Ce lien est valable 72 heures. Si vous n'êtes pas à l'origine de cette demande,
          vous pouvez ignorer cet email.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; text-align: center;">
          Javelaud — Cabinet d'expertise juridique
        </p>
      </div>
    </body>
    </html>
    """
    _send_email(to_email, subject, html)


def send_status_update_email(to_email: str, prenom: str, status_label: str) -> None:
    subject = f"Javelaud — Mise à jour de votre dossier SASU"
    dashboard_url = f"{APP_URL}/client/dashboard"
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
      <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px;">
        <h1 style="color: #0f1f45;">Javelaud</h1>
        <h2 style="color: #1e3a8a;">Bonjour {prenom},</h2>
        <p style="color: #374151; line-height: 1.6;">
          Votre dossier de création de SASU vient d'être mis à jour :
        </p>
        <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 4px; margin: 20px 0;">
          <strong style="color: #1e3a8a;">Nouvelle étape :</strong>
          <span style="color: #374151;"> {status_label}</span>
        </div>
        <a href="{dashboard_url}"
           style="background: #1e3a8a; color: white; padding: 12px 24px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
          Voir mon dossier →
        </a>
      </div>
    </body>
    </html>
    """
    _send_email(to_email, subject, html)
