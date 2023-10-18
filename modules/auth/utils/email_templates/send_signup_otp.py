from modules.auth.utils.ses import send_email_ses

def send_signup_otp(email_id, otp):
    subject = "Your OTP at Simple OTP"
    body_html = f"""<!DOCTYPE html>
      <html>
        <body>
          <p>Use this code to verify your login at Simple OTP</p>
          <p><h1>{otp}</h1></p>
        </body>
      </html>
    """

    send_email_ses(**{
        "subject": "Your OTP at Simple OTP",
        "body_html": email_id,
        "recipient": "anshikanbd@gmail.com",
        "sender": "girishkumargupta3@gmail.com",
    })