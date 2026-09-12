"""Feedback on a demo page: conversation-shaped, not survey-shaped.

Two tiers, deliberately:

1. **Sentiment** (``st.feedback``) — one click, no identity, no friction. Honest about
   what it is: a weak signal. Against the strategy's evidence ladder this is level 0-1,
   "recognition only".
2. **A conversation starter** — an optional note answering "what are you trying to
   measure or decide?". A reader describing their own problem is a level-2 signal, and
   the only kind of feedback worth acting on.

Sink: Streamlit Community Cloud's filesystem is **ephemeral**, so appending to a local
file silently loses everything on the next restart or redeploy. This module never
pretends otherwise. Configure ``FEEDBACK_ENDPOINT`` in ``st.secrets`` to POST somewhere
real; with nothing configured it falls back to a ``mailto:`` link, which needs no
infrastructure and always works.

Secrets (all optional), in ``.streamlit/secrets.toml`` locally or the app's Secrets pane:

    CONTACT_EMAIL = "you@example.com"
    FEEDBACK_ENDPOINT = "https://formspree.io/f/xxxxxxx"
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import streamlit as st


def _secret(key: str) -> str:
    try:
        return str(st.secrets.get(key, "") or "")
    except Exception:  # no secrets configured at all
        return ""


def _post(endpoint: str, payload: dict) -> tuple[bool, str]:
    """Best-effort POST. A failed send must never break the demo."""
    try:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                # Some form providers reject unknown user agents; identify honestly.
                "User-Agent": "cvprofiles-demo/0.1",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300, f"HTTP {response.status}"
    except Exception as exc:
        return False, type(exc).__name__


def _deliver(payload: dict, subject: str, body: str) -> None:
    """Send to the configured endpoint, else hand the reader a mailto link."""
    endpoint = _secret("FEEDBACK_ENDPOINT")
    email = _secret("CONTACT_EMAIL")

    if endpoint:
        ok, info = _post(endpoint, payload)
        if ok:
            st.success("Sent. Thank you — I read these.", icon=":material/check:")
            return
        st.warning(
            f"The endpoint refused it ({info}). Nothing is stored in the app itself, "
            "so please use the email link below.",
            icon=":material/warning:",
        )

    if email:
        href = "mailto:" + email + "?" + urllib.parse.urlencode(
            {"subject": subject, "body": body}
        )
        st.link_button("Send by email instead", href, icon=":material/mail:")
    else:
        st.caption(
            "No delivery route is configured, so this is inert. Set "
            "`FEEDBACK_ENDPOINT` or `CONTACT_EMAIL` in the app's secrets to turn it on."
        )


def sentiment(page: str, prompt: str = "Did this land?") -> None:
    """The zero-friction tier: one click, nothing stored in-app."""
    st.caption(prompt)
    rating = st.feedback("thumbs", key=f"fb_sentiment_{page}")
    if rating is None:
        return
    # st.feedback returns the widget's option index, not a semantic value.
    _deliver(
        {"page": page, "kind": "sentiment", "option_index": rating},
        f"cvprofiles demo — feedback on {page}",
        f"page: {page}\nsentiment option index: {rating}\n",
    )


def conversation_hook(page: str, question: str) -> None:
    """The high-intent tier: an open invitation, no obligation, no dark patterns."""
    with st.expander("Tell me what you're trying to measure", icon=":material/forum:"):
        st.caption(
            "This is the useful kind of feedback. If you describe your own problem here, "
            "I will actually read it."
        )
        with st.form(key=f"fb_note_{page}", clear_on_submit=True):
            note = st.text_area(question, height=110, placeholder="…")
            email = st.text_input(
                "Email (optional)",
                help="Only needed if you want a reply. Not required to send.",
            )
            sent = st.form_submit_button("Send", icon=":material/send:")
        if sent:
            if not note.strip():
                st.warning("Nothing to send yet — add a line above.", icon=":material/edit:")
                return
            subject = f"cvprofiles demo — a measurement problem ({page})"
            body = f"page: {page}\n\n{note.strip()}\n\nreply to: {email.strip() or '(none given)'}\n"
            _deliver(
                {
                    "page": page,
                    "kind": "note",
                    "note": note.strip(),
                    "email": email.strip(),
                },
                subject,
                body,
            )


def footer(page: str, question: str = "What are you trying to measure or decide?") -> None:
    """Both tiers, plus the honest framing of what this is for."""
    st.divider()
    st.markdown("### Feedback")
    sentiment(page)
    conversation_hook(page, question)
    st.caption(
        "Nothing is stored inside this app — it runs on ephemeral hosting, so the only "
        "durable route is the one above."
    )
