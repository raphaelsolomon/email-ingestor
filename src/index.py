"""
index.py — the human-facing Streamlit review app. Wraps everything
ingest.py, judge.py, store.py, and export_evalutation.py already built.
It reads the same database and writes corrections. Parsing only ever
happens in ingest.py; the one deliberate exception is the "Run Judge
now" demo button below, which calls judge.py directly so a reviewer
can trigger a judge pass without leaving the browser — the same call
app.py already makes from the CLI, just reachable from the UI too.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE importing other modules so they can access environment variables
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Now import after .env is loaded
import hashlib
import json
from datetime import datetime, timezone

import streamlit as st

import ingest
import judge
import store

FALLBACK_EMAILS_DIR = PROJECT_ROOT / "Emails"
FALLBACK_DB_PATH = str(PROJECT_ROOT / "data" / "mailing.db")

_MODULE_INIT_ERROR = None
EMAILS_DIR = FALLBACK_EMAILS_DIR
DB_PATH = FALLBACK_DB_PATH


def _load_streamlit_secrets_into_os_environ() -> None:
    """
    Streamlit Community Cloud stores secrets in st.secrets (TOML) rather than
    shell environment variables. Copy them into os.environ so the existing
    os.getenv(...) fallbacks in ingest/judge/llm_client keep working.
    Only runs when streamlit is actually in a running context (has st.secrets).
    """
    try:
        secrets = st.secrets
    except Exception:
        return
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL",
                "DB_PATH", "EMAILS_DIR", "MODEL_ENDPOINT_APPROVED"):
        try:
            if key in secrets:
                value = secrets[key]
                if value is None:
                    continue
                os.environ.setdefault(key, str(value))
        except Exception:
            continue


def _safe_warn_once(key: str, message: str) -> None:
    """Show a st.warning exactly once per session; gracefully skips if
    st.session_state is not yet available (module-import-time code paths)."""
    try:
        state = st.session_state
    except Exception:
        return
    flag = f"_warned_{key}"
    if not state.get(flag):
        st.warning(message)
        state[flag] = True


def _resolve_env_dir(env_name: str, fallback: Path, warn_label: str) -> Path:
    """
    Try to use a directory path from .env. If the env var is not set,
    the path is not a valid absolute path on this machine, or the
    directory can't be created, fall back to the project-local default
    and surface a warning in the UI so the operator knows.
    """
    raw = os.environ.get(env_name)
    if not raw:
        return fallback
    p = Path(raw)
    # On Windows, a POSIX path like "/Users/foo/Emails" resolves to the
    # drive root of a different user's profile; it's almost never valid.
    # Treat a path that starts with "/" without "//" (i.e. not UNC) as
    # a cross-platform mistake, unless it actually exists on disk.
    try:
        is_posix_style = not str(p).startswith("//") and raw.startswith("/")
        if is_posix_style and not p.exists():
            raise FileNotFoundError(f"POSIX-style path on this OS: {raw}")
        p.mkdir(parents=True, exist_ok=True)
        # Try an actual write probe to catch Access Denied before UI action.
        probe = p / f".write_probe_{os.getpid()}.tmp"
        try:
            probe.write_bytes(b"ok")
            probe.unlink()
        except OSError as e:
            raise PermissionError(f"write probe failed: {e}") from e
        return p
    except (OSError, ValueError) as e:
        _safe_warn_once(
            env_name,
            f"{warn_label} path {env_name}={raw!r} is not usable here "
            f"({type(e).__name__}: {e}). Falling back to {fallback}.",
        )
        return fallback


def _resolve_db_path() -> str:
    raw = os.environ.get("DB_PATH")
    if not raw:
        return FALLBACK_DB_PATH
    candidate = PROJECT_ROOT / raw if not Path(raw).is_absolute() else Path(raw)
    # A non-existent DB path is actually fine (store.connect creates it),
    # but the *parent directory* must exist or be creatable.
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return str(candidate)
    except OSError as e:
        _safe_warn_once(
            "DB_PATH",
            f"DB_PATH={raw!r} parent dir is not usable here "
            f"({type(e).__name__}: {e}). Falling back to {FALLBACK_DB_PATH}.",
        )
        return FALLBACK_DB_PATH


# Only AFTER all helper definitions: run init logic. Any failure is captured
# (so streamlit still gets to main()) and surfaced as an error banner there.
try:
    _load_streamlit_secrets_into_os_environ()
    EMAILS_DIR = _resolve_env_dir("EMAILS_DIR", FALLBACK_EMAILS_DIR, "Emails")
    DB_PATH = _resolve_db_path()
except Exception as _e:
    _MODULE_INIT_ERROR = _e
    EMAILS_DIR = FALLBACK_EMAILS_DIR
    DB_PATH = FALLBACK_DB_PATH
PRIORITY_LABELS = {
    1: "1 Immediate Attention",
    2: "2 Action / Decision Required Today",
    3: "3 Reference / Observation",
    4: "4 Filter / No Executive Attention",
}
JUDGEMENT_FIELDS = ["priority", "uncertainty", "who", "what", "why", "action", "deadline"]

JUDGEMENT_TYPES = {
    "priority": int,
    "uncertainty": lambda v: None if v in (None, "", "None") else str(v),
    "who": str,
    "what": str,
    "why": str,
    "action": str,
    "deadline": lambda v: None if v in (None, "", "None") else str(v),
}


@st.cache_resource
def get_conn():
    # check_same_thread=False: Streamlit reruns your script on a
    # different thread each time, but sqlite3 connections are
    # thread-bound by default. Without this your second click crashes.
    return store.connect(DB_PATH)


def effective_judgement(conn, judgement) -> dict:
    # Same idea as export_evaluation.py's _effective_judgement:
    # original fields, then corrections overwrite theirs.
    effective = {f: judgement[f] for f in JUDGEMENT_FIELDS}
    for c in store.list_corrections_for_judgement(conn, judgement["id"]):
        effective[c["field"]] = c["new_value"]
    return effective


def render_highlighted(text: str, quotes: list) -> str:
    # Wraps every evidence quote in <mark> so it's highlighted when
    # shown as HTML. This is literally what makes evidence "traceable"
    # for a reviewer instead of just a quote sitting in a side panel.
    import html
    text = text or ""
    escaped = html.escape(text)
    for q in sorted(set(quotes), key=len, reverse=True):
        if q:
            escaped = escaped.replace(html.escape(q), f"<mark>{html.escape(q)}</mark>")
    return escaped.replace("\n", "<br>")


def queue_rows(conn):
    # Group threads into topics and categorize by priority and review status.
    rows = {
        "priority_1": [],
        "priority_2": [],
        "priority_3": [],
        "priority_4": [],
        "uncertain": [],
        "unreadable": [],
        "unjudged": [],
    }
    for topic in store.list_topics(conn):
        topic_threads = []
        topic_unjudged = 0
        topic_unreadable = 0
        all_judgements = []
        all_effective = []

        for thread_id in topic["thread_ids"]:
            messages = store.list_messages_by_thread(conn, thread_id)
            if not messages or not any(m["parse_status"] == "ok" for m in messages):
                topic_unreadable += 1
                continue

            judgement = store.latest_judgement_for_thread(conn, thread_id)
            if judgement is None:
                topic_unjudged += 1
                continue

            eff = effective_judgement(conn, judgement)
            all_judgements.append(judgement)
            all_effective.append(eff)
            topic_threads.append({
                "thread": store.get_thread(conn, thread_id),
                "judgement": judgement,
                "effective": eff,
                "subject": messages[-1]["subject"],
            })

        if topic_unreadable == len(topic["thread_ids"]):
            for thread_id in topic["thread_ids"]:
                msgs = store.list_messages_by_thread(conn, thread_id)
                if msgs:
                    m = msgs[0]
                    rows["unreadable"].append({
                        "topic": topic,
                        "filename": m["filename"],
                        "error": m["parse_error"],
                    })
            continue

        if not topic_threads:
            if topic_unjudged > 0:
                rows["unjudged"].append({"topic": topic, "thread_count": topic_unjudged})
            continue

        max_priority = min([e["priority"] for e in all_effective if e["priority"]])
        has_uncertain = any(j["review_status"] == "needs_evidence" for j in all_judgements)

        topic_entry = {
            "topic": topic,
            "threads": topic_threads,
            "max_priority": max_priority,
            "has_uncertain": has_uncertain,
        }

        if has_uncertain:
            rows["uncertain"].append(topic_entry)
        elif max_priority == 1:
            rows["priority_1"].append(topic_entry)
        elif max_priority == 2:
            rows["priority_2"].append(topic_entry)
        elif max_priority == 3:
            rows["priority_3"].append(topic_entry)
        else:
            rows["priority_4"].append(topic_entry)

    return rows


def effective_judgement(conn, judgement) -> dict:
    # Same idea as export_evaluation.py's _effective_judgement:
    # original fields, then corrections overwrite theirs.
    # Corrections are stored as strings, so cast each field back to its
    # declared type (priority -> int, deadline/uncertainty -> optional str).
    effective = {f: judgement[f] for f in JUDGEMENT_FIELDS}
    for c in store.list_corrections_for_judgement(conn, judgement["id"]):
        effective[c["field"]] = _coerce(c["field"], c["new_value"])
    return effective


def render_upload(conn):
    # Demo convenience only — still calls ingest.run_ingest(), so
    # Ingest remains the only thing that ever parses a file.
    with st.expander("Upload new .msg files (demo only)"):
        uploaded = st.file_uploader(
            "Drop .msg files here",
            type="msg",
            accept_multiple_files=True,
            key="upload_new_msg",
        )

        def _do_ingest():
            files = st.session_state.get("upload_new_msg") or []
            if not files:
                st.session_state.setdefault("toast_warning", "No files were selected.")
                return
            EMAILS_DIR.mkdir(parents=True, exist_ok=True)
            written = []
            for f in files:
                target = EMAILS_DIR / f.name
                target.write_bytes(f.getvalue())
                written.append(str(target))
            try:
                result = ingest.run_ingest(str(EMAILS_DIR), DB_PATH)
            except Exception as e:
                st.session_state["toast_error"] = f"Ingest failed: {type(e).__name__}: {e}"
                return
            st.session_state["toast_success"] = f"Ingested {len(written)} file(s): {result}"
            # Force refresh of the DB connection after write
            get_conn.clear()

        st.button(
            "Ingest uploaded files",
            key="ingest_uploaded_btn",
            on_click=_do_ingest,
            type="primary",
            disabled=not uploaded,
        )

        def _do_judge():
            model = os.getenv("ANTHROPIC_MODEL", "MiniMax-M3")
            try:
                result = judge.run_judge(DB_PATH, model)
            except Exception as e:
                st.session_state["toast_error"] = f"Judge failed: {type(e).__name__}: {e}"
                return
            st.session_state["toast_success"] = f"Judge run: {result}"
            get_conn.clear()

        st.caption("Judges every thread still waiting in \"Not yet judged\", not just the one above.")
        st.button(
            "Run Judge now",
            key="run_judge_btn",
            on_click=_do_judge,
        )


def _render_pending_toasts() -> None:
    """Render one-shot toasts stored in session_state (survive a st.rerun())."""
    for key, kind in (
        ("toast_success", "success"),
        ("toast_warning", "warning"),
        ("toast_error", "error"),
    ):
        msg = st.session_state.pop(key, None)
        if msg:
            fn = getattr(st, kind)
            fn(msg)


def _coerce(field: str, value):
    cast = JUDGEMENT_TYPES.get(field, str)
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _find_source_quote(conn, message_id, source_field, quote):
    """
    Verifies `quote` appears verbatim somewhere in the given (message, source_field).
    For source_field == "body" we scan every segment, since _source_text requires a
    specific segment_index and returns None when segment_index is None.

    Returns (source_text, segment_index, start_offset) for the first match found,
    or (None, None, None) if no match.
    """
    if not quote:
        return None, None, None
    if source_field == "body":
        for s in store.list_segments_by_message(conn, message_id):
            if quote in s["body"]:
                return s["body"], s["idx"], s["body"].find(quote)
        return None, None, None
    from judge import _source_text
    result = _source_text(conn, message_id, source_field, None)
    text = result[0] if result else ""
    if text and quote in text:
        return text, None, text.find(quote)
    return None, None, None


def render_queue(conn):
    st.title("Executive Email Intelligence — Queue")
    render_upload(conn)
    rows = queue_rows(conn)

    def render_priority_section(title, topics, show_alert=False):
        st.subheader(title)
        if not topics:
            st.caption("None.")
            return
        for topic_entry in topics:
            topic = topic_entry["topic"]
            topic_label = f"{topic['subject']}" + (f" ({len(topic_entry['threads'])} thread(s))" if len(topic_entry['threads']) > 1 else "")

            if show_alert and topic_entry["threads"]:
                first_eff = topic_entry["threads"][0]["effective"]
                alert_preview = ""
                if first_eff.get("who"):
                    alert_preview += f"Who: {first_eff['who']} | "
                if first_eff.get("action"):
                    alert_preview += f"Action: {first_eff['action']}"
                if alert_preview:
                    alert_preview = alert_preview.rstrip(" | ")
                    topic_label += f"\n{alert_preview}"

            with st.expander(topic_label, expanded=False):
                st.write(f"**From:** {topic['sender']}")
                if show_alert and topic_entry["threads"]:
                    first_eff = topic_entry["threads"][0]["effective"]
                    if first_eff.get("who"):
                        st.write(f"- **Who:** {first_eff['who']}")
                    if first_eff.get("what"):
                        st.write(f"- **What:** {first_eff['what']}")
                    if first_eff.get("why"):
                        st.write(f"- **Why:** {first_eff['why']}")
                    if first_eff.get("action"):
                        st.write(f"- **Action:** {first_eff['action']}")
                    if first_eff.get("deadline"):
                        st.write(f"- **Deadline:** {first_eff['deadline']}")

                st.write(f"**{len(topic_entry['threads'])} thread(s):**")
                for t in topic_entry["threads"]:
                    if st.button(t["subject"], key=f"q_{t['thread']['id']}"):
                        st.session_state.selected_thread_id = t["thread"]["id"]
                        st.rerun()

    render_priority_section("🚨 1. Immediate Attention", rows["priority_1"], show_alert=True)
    render_priority_section("⚠️ 2. Action / Decision Required Today", rows["priority_2"], show_alert=True)
    render_priority_section("📖 3. Reference / Observation", rows["priority_3"], show_alert=False)
    render_priority_section("🔕 4. Filter / No Executive Attention", rows["priority_4"], show_alert=False)

    st.subheader("❓ Uncertain")
    if not rows["uncertain"]:
        st.caption("None.")
    else:
        for topic_entry in rows["uncertain"]:
            topic = topic_entry["topic"]
            with st.expander(f"{topic['subject']} — {topic_entry['threads'][0]['judgement'].get('uncertainty', 'unclear')}"):
                for t in topic_entry["threads"]:
                    if st.button(t["subject"], key=f"q_{t['thread']['id']}_unc"):
                        st.session_state.selected_thread_id = t["thread"]["id"]
                        st.rerun()

    st.subheader("⚠️ Unreadable / Erroneous Files")
    if not rows["unreadable"]:
        st.caption("None.")
    else:
        for e in rows["unreadable"]:
            st.write(f"- {e['filename']}: {e['error']}")

    if rows["unjudged"]:
        st.subheader("⏳ Not yet judged")
        for e in rows["unjudged"]:
            with st.expander(f"{e['topic']['subject']} ({e['thread_count']} thread(s))"):
                st.write(f"**From:** {e['topic']['sender']}")
                for thread_id in e["topic"]["thread_ids"]:
                    msgs = store.list_messages_by_thread(conn, thread_id)
                    if msgs and any(m["parse_status"] == "ok" for m in msgs):
                        thread_subject = msgs[-1]["subject"]
                        if st.button(thread_subject, key=f"q_{thread_id}_uj"):
                            st.session_state.selected_thread_id = thread_id
                            st.rerun()


def render_thread(conn, thread_id):
    thread = store.get_thread(conn, thread_id)
    messages = store.list_messages_by_thread(conn, thread_id)
    judgement = store.latest_judgement_for_thread(conn, thread_id)

    if st.button("← Back to queue"):
        st.session_state.selected_thread_id = None
        st.rerun()

    st.title(thread["normalized_subject"] or "(no subject)")
    st.caption(f"grouping basis: {thread['grouping_basis']} ({thread['grouping_confidence']})")

    evidence = store.list_evidence_for_judgement(conn, judgement["id"]) if judgement else []
    quotes_by_segment = {}
    for e in evidence:
        if e["segment_id"]:
            quotes_by_segment.setdefault(e["segment_id"], []).append(e["quote"])

    st.header("Messages")
    for m in messages:
        st.subheader(f"{m['filename']} — {m['subject']}")
        if m["parse_status"] != "ok":
            st.error(f"{m['parse_status']}: {m['parse_error']}")
            continue
        for seg in store.list_segments_by_message(conn, m["id"]):
            st.markdown(render_highlighted(seg["body"], quotes_by_segment.get(seg["id"], [])), unsafe_allow_html=True)
            st.divider()

    if judgement is None:
        st.info("Not yet judged.")
        return

    eff = effective_judgement(conn, judgement)
    st.header("Judgement")
    st.write(f"**Priority:** {PRIORITY_LABELS.get(eff['priority'], 'none - needs evidence')}")
    st.write(f"**Reason:** {judgement['reason']}")
    if eff["uncertainty"]:
        st.warning(eff["uncertainty"])

    if eff["priority"] in (1, 2):
        st.subheader("Executive Alert")
        for field, label in [("who", "Who"), ("what", "What happened"), ("why", "Why it matters"),
                              ("action", "Required action"), ("deadline", "Deadline")]:
            if eff.get(field):
                st.write(f"- **{label}:** {eff[field]}")

    st.subheader("Evidence")
    for e in evidence:
        st.write(f"- [{e['field']}] \"{e['quote']}\"")

    st.subheader("Add a correction")
    st.write("**Step 1: What kind of error?**")
    error_category = st.radio("Category of error", ["Wrongly Classified", "Something Else"], key="corr_error_cat")

    if error_category == "Wrongly Classified":
        st.write("**Step 2: What should the correct category be?**")
        new_priority = st.selectbox(
            "Correct priority",
            [1, 2, 3, 4],
            format_func=lambda x: PRIORITY_LABELS[x] if x in PRIORITY_LABELS else str(x),
            key="corr_correct_priority"
        )
    else:
        new_priority = eff["priority"]

    st.write("**Step 3: Why was it wrong?**")
    description = st.text_area(
        "Describe the issue (this will help classify similar emails correctly)",
        placeholder="E.g., 'Promotional deadline, no executive action needed'",
        key="corr_description"
    )

    if st.button("Save correction", key="save_corr_btn"):
        if not description.strip():
            st.error("Please provide a description.")
            st.stop()

        now_iso = datetime.now(timezone.utc).isoformat()
        correction_id = hashlib.sha1(f"{judgement['id']}:{now_iso}".encode()).hexdigest()

        # For P3: always storing as priority correction
        store.insert_correction(conn, {
            "id": correction_id,
            "judgement_id": judgement["id"],
            "field": "priority",
            "old_value": str(eff.get("priority")),
            "new_value": str(new_priority),
            "reason": description,
            "basis": "human_input",
            "error_category": "wrongly_classified" if error_category == "Wrongly Classified" else "other",
            "semantic_summary": f"Changed from Priority {eff['priority']} to {new_priority}: {description[:100]}",
            "created_at": now_iso,
        })
        conn.commit()
        st.session_state["toast_success"] = "✅ Correction saved. It will help classify similar emails."
        st.rerun()


def main():
    st.set_page_config(page_title="Executive Email Intelligence", layout="wide")
    _render_pending_toasts()
    if _MODULE_INIT_ERROR is not None:
        st.exception(_MODULE_INIT_ERROR)
        st.error(
            "Something failed during app startup (see traceback above). "
            "This is usually caused by environment variables / Secrets not "
            "being loaded correctly. Reload after fixing to retry.",
            icon="🚨",
        )
        st.stop()
    conn = get_conn()
    if "selected_thread_id" not in st.session_state:
        st.session_state.selected_thread_id = None
    if st.session_state.selected_thread_id:
        render_thread(conn, st.session_state.selected_thread_id)
    else:
        render_queue(conn)


if __name__ == "__main__":
    main()