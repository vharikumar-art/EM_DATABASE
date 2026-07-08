from app.emails.service import build_profile_email_notification_message


def test_profile_email_notification_message_for_matches():
    message = build_profile_email_notification_message("Sales Profile", 12)

    assert "Sales Profile" in message
    assert "12" in message
    assert "email" in message


def test_profile_email_notification_message_for_no_matches():
    message = build_profile_email_notification_message("Sales Profile", 0)

    assert "Sales Profile" in message
    assert "0" in message
    assert "emails" in message
