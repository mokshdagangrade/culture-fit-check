"""Year-aware calendar facts; separate retail promotion dates from observance dates."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import re


def campaign_today():
    return datetime.now(ZoneInfo('America/New_York')).date()


def campaign_dates(text, today=None):
    today = today or campaign_today()
    if not re.search(r'black\s*friday', text, re.I):
        return {}
    first = date(today.year, 11, 1)
    thanksgiving = first + timedelta(days=(3 - first.weekday()) % 7 + 21)
    return {'Black Friday': (thanksgiving + timedelta(days=1)).isoformat()}


def calendar_instructions(text, today=None):
    today = today or campaign_today()
    return (f'Current campaign date: {today.isoformat()}. Use this year for relative occasions. '
            'Verified calendar dates: ' + str(campaign_dates(text, today)) + '. '
            'Use verified dates instead of dates recalled from training or older drafts. '
            'A brand can run a promotion on a different date; label that as the promotion date, '
            'never as the official observance date. Do not invent sale dates or discounts.')


NOVEMBER_DATE = re.compile(r'\bNov(?:ember)?\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?\b', re.I)


def correct_campaign_dates(text, original_brief='', today=None):
    """Repair recalled observance dates only when the brief supplies no distinct sale date.

    Other brand dates are preserved; this is not a blanket date substitution.
    """
    facts = campaign_dates(text + ' ' + original_brief, today)
    if not facts or NOVEMBER_DATE.search(original_brief) or re.search(r'\b20\d{2}-\d{2}-\d{2}\b', original_brief):
        return text
    actual = date.fromisoformat(facts['Black Friday'])
    def replace(match):
        return f'November {actual.day}' + (f', {actual.year}' if match.group(2) else '')
    # Only a date tied directly to Black Friday or a calendar CTA, not every date in a campaign.
    pattern = re.compile(r'(\bBlack\s*Friday[^.!?\n]{0,80}?|\bMark your calendars[^.!?\n]{0,30}?)(' + NOVEMBER_DATE.pattern + ')', re.I)
    return pattern.sub(lambda m: m.group(1) + NOVEMBER_DATE.sub(replace, m.group(2)), text)
