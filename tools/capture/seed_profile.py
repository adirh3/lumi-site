"""Seeds an isolated, synthetic Lumi profile for the site's recordings: the sample user "Alex", the checkout-api,
weather-cli and Home projects, and a few past chats (among them the expenses chat in the "Files" screenshot). It
never touches a real Lumi profile: point LUMI_APPDATA_DIR at the profile folder when launching Lumi (launch.ps1).

usage: python tools/capture/seed_profile.py <profile_dir> <demo_dir> [--light]
  profile_dir  the isolated profile (replaced); Lumi keeps its data in <profile_dir>/Lumi
  demo_dir     the folder make_samples.py created the sample projects in
  --light      light theme instead of dark
"""
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(ARGS) < 2:
    sys.exit(__doc__)
PROFILE = Path(ARGS[0]).resolve()
APPDIR = PROFILE / "Lumi"
DEMO = Path(ARGS[1]).resolve()
REPO = DEMO / "checkout-api"
WEATHER = DEMO / "weather-cli"
DOCS = DEMO / "Documents"
THEME_DARK = "--light" not in sys.argv

TZ = timezone(timedelta(hours=2))
# Yesterday, so the sample chats group under "Yesterday" and "Previous 7 Days" on the day of recording.
DAY = datetime.combine(datetime.now(TZ).date() - timedelta(days=1), datetime.min.time(), tzinfo=TZ)


def at(h, m, s=0, day_offset=0):
    return (DAY + timedelta(days=day_offset, hours=h, minutes=m, seconds=s)).isoformat()


def gid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "lumi-site-demo/" + name))


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def make_spreadsheet():
    DOCS.mkdir(parents=True, exist_ok=True)
    receipts = DOCS / "Receipts"
    receipts.mkdir(exist_ok=True)
    out = DOCS / "October-Expenses.xlsx"
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Receipts"
        ws.append(["Date", "Merchant", "Category", "Amount"])
        rows = [
            ("2026-10-02", "Green Market", "Groceries", 84.20),
            ("2026-10-04", "City Metro", "Transport", 60.00),
            ("2026-10-07", "Corner Bistro", "Dining", 46.80),
        ]
        for row in rows:
            ws.append(row)
        wb.save(out)
    except ImportError:
        out.write_bytes(b"")
    return out


# ── Chats ──────────────────────────────────────────────────────────────────────
def msg(name, role, content, ts, **extra):
    m = {"id": gid(name), "role": role, "content": content, "timestamp": ts}
    m.update(extra)
    return m


def tool(name, tool_name, args, ts, output=None, duration_ms=900, status="Completed"):
    started = datetime.fromisoformat(ts)
    return msg(
        name, "tool", json.dumps(args), ts,
        toolName=tool_name, toolCallId="call_" + name, toolStatus=status,
        toolOutput=output, toolStartedAt=started.isoformat(), toolDurationMs=duration_ms,
    )


def expenses_chat(sheet):
    receipts = str(DOCS / "Receipts")
    listing = "\n".join([
        "Name                          Length",
        "----                          ------",
        "2026-10-02 Green Market.pdf    48211",
        "2026-10-04 City Metro.pdf      30542",
        "2026-10-07 Corner Bistro.jpg  812004",
        "2026-10-09 Hardware Hub.pdf    51377",
        "…                                    ",
        "14 files",
    ])
    return [
        msg("exp-user", "user",
            "Turn the receipts in my Receipts folder into an October expense sheet, grouped by category.",
            at(10, 12, 0), author="Alex"),
        tool("exp-intent-1", "report_intent", {"intent": "Reading the receipts"}, at(10, 12, 4), duration_ms=40),
        tool("exp-list", "powershell", {
            "command": f"Get-ChildItem \"{receipts}\" -File | Select-Object Name, Length",
            "description": "List the receipts"}, at(10, 12, 6), output=listing, duration_ms=850),
        tool("exp-extract", "powershell", {
            "command": "python extract_receipts.py Receipts",
            "description": "Read totals from each receipt"}, at(10, 12, 9),
            output="Read 14 receipts (2 photos with low contrast)\nTotal: 1284.60", duration_ms=9600),
        tool("exp-intent-2", "report_intent", {"intent": "Building the spreadsheet"}, at(10, 12, 21), duration_ms=40),
        tool("exp-build", "powershell", {
            "command": "python build_expense_sheet.py",
            "description": "Build the expense spreadsheet"}, at(10, 12, 23),
            output=f"Saved {sheet.name}", duration_ms=2100),
        tool("exp-announce", "announce_file", {"filePath": str(sheet)}, at(10, 12, 27), output=str(sheet), duration_ms=30),
        msg("exp-answer", "assistant",
            "Your **October expense sheet** is ready: 14 receipts, **$1,284.60** in total, one row per receipt "
            "and a summary by category.\n\n"
            "```chart\n"
            "{\"type\":\"donut\",\"labels\":[\"Groceries\",\"Dining\",\"Transport\",\"Home\",\"Other\"],"
            "\"series\":[{\"name\":\"October\",\"values\":[486.2,312.4,201.0,190.5,94.5]}],"
            "\"donutCenterValue\":\"$1,284.60\",\"donutCenterLabel\":\"14 receipts\"}\n"
            "```\n\n"
            "Two receipts were low-contrast photos. I read their totals, but marked them in the sheet so you can "
            "double-check them.",
            at(10, 12, 33), author="Lumi", model="gpt-6-luna", isProgress=False),
    ]


def short_chat(name, user_text, answer, h, m, day_offset=0):
    return [
        msg(name + "-u", "user", user_text, at(h, m, 0, day_offset), author="Alex"),
        msg(name + "-a", "assistant", answer, at(h, m + 1, 0, day_offset), author="Lumi", model="gpt-6-luna", isProgress=False),
    ]


def main():
    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    (APPDIR / "chats").mkdir(parents=True)
    sheet = make_spreadsheet()

    coding_project = gid("project-checkout")
    home_project = gid("project-home")

    chats = [
        dict(key="expenses", title="October expenses from receipts", project=home_project, pinned=False,
             messages=expenses_chat(sheet), follow=["Add a monthly budget column", "Email me the sheet"],
             context=(9210, 200000)),
        dict(key="release", title="Draft release notes for 1.8", project=coding_project, pinned=False,
             messages=short_chat("release", "Draft short release notes from the commits since v1.7.",
                                 "Here's a short draft grouped into **New**, **Fixed** and **Improved**, written for users rather than contributors.",
                                 9, 40)),
        dict(key="health", title="Add a health check endpoint", project=coding_project, pinned=False,
             messages=short_chat("health", "Add a /health endpoint that also checks the pricing service.",
                                 "Added `GET /health`: it reports the API's status and pings the pricing service with a one-second timeout. The change is uncommitted, ready for your review.",
                                 17, 35, day_offset=-2)),
        dict(key="empty-cart", title="Return 400 for empty carts", project=coding_project, pinned=False,
             messages=short_chat("empty-cart", "Checkout throws a 500 when the cart is empty. Make it a clear 400 instead.",
                                 "Checkout now returns **400** with \"Cart is empty\" instead of throwing. I committed it as \"Return 400 for empty carts\".",
                                 16, 10, day_offset=-4)),
        dict(key="sku-review", title="Review the SKU search ranking change", project=coding_project, pinned=False,
             messages=short_chat("sku-review", "Review Priya's change to how search ranks exact SKU matches.",
                                 "It looks right: exact SKU matches now rank first and partial matches keep their order. One suggestion: trim whitespace before comparing.",
                                 11, 20, day_offset=-6)),
        dict(key="porto", title="Plan a weekend in Porto", project=None, pinned=False,
             messages=short_chat("porto", "Plan a relaxed weekend in Porto for two.",
                                 "Keep one main thing each day: the riverside and a port cellar on Saturday, Serralves on Sunday, with long lunches in between.",
                                 21, 5, day_offset=-1)),
        dict(key="desk", title="Compare two standing desks", project=None, pinned=False,
             messages=short_chat("desk", "Compare these two standing desks for a small room.",
                                 "The narrower frame fits your room better; the other is steadier at full height. I'd pick the narrower one.",
                                 18, 20, day_offset=-1)),
        dict(key="notes", title="Summarize the design review", project=None, pinned=False,
             messages=short_chat("notes", "Summarize the design review notes in five bullets.",
                                 "Five decisions, two open questions and one owner per follow-up.",
                                 16, 2, day_offset=-2)),
    ]

    index = []
    for chat in chats:
        messages = chat["messages"]
        chat_id = gid("chat-" + chat["key"])
        (APPDIR / "chats" / f"{chat_id}.json").write_text(json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8")
        last = messages[-1]
        entry = {
            "id": chat_id,
            "title": chat["title"],
            "projectId": chat["project"],
            "createdAt": messages[0]["timestamp"],
            "updatedAt": last["timestamp"],
            "messageCount": len(messages),
            "preview": last["content"][:140],
            "lastModelUsed": "gpt-6-luna",
            "isPinned": chat["pinned"],
        }
        if chat.get("follow"):
            entry["followUpSuggestions"] = chat["follow"]
            entry["followUpSuggestionAssistantMessageId"] = last["id"]
        if chat.get("context"):
            entry["contextCurrentTokens"], entry["contextTokenLimit"] = chat["context"]
            entry["hasExactContextUsage"] = True
        index.append(entry)

    data = {
        "settings": {
            "userName": "Alex",
            "isOnboarded": True,
            "language": "en",
            "isDarkTheme": THEME_DARK,
            "followSystemTheme": False,
            "windowMaterial": "solid",
            "windowWidth": 1980,
            "windowHeight": 1290,
            "isMaximized": False,
            "uiScalePercent": 150,
            "startMinimized": True,
            "allowAppSetupSuggestions": False,
            "offerCopiedCapabilities": False,
            "notificationsEnabled": False,
            "launchAtStartup": False,
            "minimizeToTray": False,
            "autoGenerateTitles": True,
            "suggestFollowUps": True,
            "enableMemoryAutoSave": False,
            "enableMemoryAutoMaintenance": False,
            "enableDailyBriefs": False,
            "remoteAccessEnabled": False,
            "personalSkillDirectories": [],
            "preferredModel": "gpt-6-luna",
        },
        "chats": index,
        "skills": [],
        "agents": [],
        "memories": [],
        "mcpServers": [],
        "backgroundJobs": [],
        "projects": [
            {"id": coding_project, "name": "checkout-api",
             "instructions": "The shop's cart and checkout service, an ASP.NET Core minimal API. Production logs are in logs/.",
             "workingDirectory": str(REPO)},
            {"id": gid("project-weather"), "name": "weather-cli",
             "instructions": "A small .NET command-line weather client. Keep changes focused and tested.",
             "workingDirectory": str(WEATHER)},
            {"id": home_project, "name": "Home",
             "instructions": "Household paperwork, budgets and plans."},
        ],
    }
    (APPDIR / "data.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({"profile": str(PROFILE), "repo": str(REPO), "dark": THEME_DARK}))


if __name__ == "__main__":
    main()


