import smtplib, ssl
from email.message import EmailMessage
class SendMail(object):
    def __init__(self):
        self.port = 587 
        self.smtp_server = "smtp.gmail.com"
        self.sender_email = "rerollpricess23@gmail.com"
        self.receiver_email = "huytai2k1@gmail.com"
        self.password = "pbzazighnokhukvs"
        self.subject = "Video Stream App Notification"
    def send(self, content):
        em = EmailMessage()
        em["From"] = self.sender_email
        em["To"] = self.receiver_email 
        em["Subject"] = self.subject
        em.set_content(content)
        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_server, self.port) as server:
            server.ehlo()  # Can be omitted
            server.starttls(context=context)
            server.ehlo()  # Can be omitted
            server.login(self.sender_email, self.password)
            server.sendmail(self.sender_email, self.receiver_email, em.as_string())