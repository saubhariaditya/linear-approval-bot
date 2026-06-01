from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ── Configuration (loaded from Environment Variables) ──────────
LINEAR_API_KEY   = os.environ.get("LINEAR_API_KEY")
SLACK_BOT_TOKEN  = os.environ.get("SLACK_BOT_TOKEN")
VINAY_LINEAR_ID  = os.environ.get("VINAY_LINEAR_ID")
VINAY_SLACK_ID   = os.environ.get("VINAY_SLACK_ID")
APPROVAL_STATE   = "Ready for Approval"
LINEAR_API_URL   = "https://api.linear.app/graphql"
# ───────────────────────────────────────────────────────────────


def assign_to_vinay(issue_id):
    """Reassign the Linear issue to Vinay."""
    mutation = """
    mutation UpdateIssue($id: String!, $assigneeId: String!) {
        issueUpdate(id: $id, input: { assigneeId: $assigneeId }) {
            success
            issue { id title url identifier }
        }
    }
    """
    resp = requests.post(
        LINEAR_API_URL,
        json={"query": mutation, "variables": {"id": issue_id, "assigneeId": VINAY_LINEAR_ID}},
        headers={"Authorization": LINEAR_API_KEY, "Content-Type": "application/json"},
    )
    return resp.json()


def notify_vinay_on_slack(title, url, identifier):
    """Send Vinay a Slack DM about the ticket needing approval."""
    message = (
        f":bell: *Approval Required!*\n\n"
        f"Hey Vinay! A ticket has been assigned to you for approval.\n\n"
        f"*Ticket:* {identifier} — {title}\n"
        f"*Link:* <{url}|View Ticket>\n\n"
        f"Please review and move to *Done* once approved. :white_check_mark:"
    )
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        json={"channel": VINAY_SLACK_ID, "text": message},
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    return resp.json()


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}

    # Only care about Issue create / update events
    if data.get("type") != "Issue" or data.get("action") not in ("create", "update"):
        return jsonify({"status": "ignored"}), 200

    issue   = data.get("data", {})
    state   = issue.get("state", {}).get("name", "")

    if state != APPROVAL_STATE:
        return jsonify({"status": "not approval state"}), 200

    issue_id         = issue.get("id")
    issue_title      = issue.get("title", "Untitled")
    issue_identifier = issue.get("identifier", "")
    issue_url        = issue.get("url", "")

    assign_result = assign_to_vinay(issue_id)
    slack_result  = notify_vinay_on_slack(issue_title, issue_url, issue_identifier)

    print(f"[OK] {issue_identifier} → assigned to Vinay | Slack: {slack_result.get('ok')}")
    return jsonify({"status": "processed", "issue": issue_identifier}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Linear Approval Bot is running! ✅"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
