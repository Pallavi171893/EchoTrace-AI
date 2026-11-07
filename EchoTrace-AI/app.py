
import os
import re
import sqlite3
import logging
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify
from hindsight_client import Hindsight

# ---------------- CONFIGURATION ----------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-demo-key")

logging.basicConfig(level=logging.INFO)

DATABASE = "database/echotrace.db"

HINDSIGHT_URL = os.environ.get(
    "HINDSIGHT_API_URL",
    "http://localhost:8888"
)

BANK_ID = "echotrace"

executor = ThreadPoolExecutor(max_workers=2)

try:
    memory_client = Hindsight(base_url=HINDSIGHT_URL)
except Exception:
    memory_client = None
    app.logger.exception("Hindsight initialization failed")


# ---------------- DATABASE ----------------

def get_db():
    os.makedirs("database", exist_ok=True)

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            department TEXT NOT NULL,
            problem TEXT NOT NULL,
            workaround TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            decision TEXT NOT NULL,
            outcome TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


initialize_database()


# ---------------- HINDSIGHT MEMORY ----------------

def run_memory_method(method, **kwargs):
    if memory_client is None:
        raise RuntimeError("Hindsight client unavailable")

    future = executor.submit(method, **kwargs)

    return future.result(timeout=90)


def initialize_memory():
    if memory_client is None:
        return

    try:
        run_memory_method(
            memory_client.create_bank,
            bank_id=BANK_ID,
            name="EchoTrace AI"
        )

        app.logger.info("Hindsight bank initialized")

    except Exception as error:
        app.logger.info("Bank initialization: %s", error)


def retain_memory(content, context):
    try:
        run_memory_method(
            memory_client.retain,
            bank_id=BANK_ID,
            content=content,
            context=context
        )

        return True

    except Exception:
        app.logger.exception("Hindsight retention failed")
        return False


def recall_memories(query):
    try:
        return run_memory_method(
            memory_client.recall,
            bank_id=BANK_ID,
            query=query
        )

    except Exception:
        app.logger.exception("Hindsight recall failed")
        return None


def clean_memory_result(memory_result):
    if memory_result is None:
        return []

    results = getattr(memory_result, "results", None)

    if results is None and isinstance(memory_result, dict):
        results = memory_result.get("results", [])

    if not results:
        return []

    memories = []

    for item in results:

        if isinstance(item, dict):
            memory_id = item.get("id", "")
            memory_type = item.get("type", "experience")
            memory_text = item.get(
                "text",
                item.get("content", "")
            )

        else:
            memory_id = getattr(item, "id", "")
            memory_type = getattr(item, "type", "experience")
            memory_text = getattr(item, "text", str(item))

        memories.append({
            "id": str(memory_id),
            "type": str(memory_type),
            "text": str(memory_text)
        })

    return memories


# ---------------- INCIDENT MANAGEMENT ----------------

def get_incidents():
    connection = get_db()

    rows = connection.execute("""
        SELECT * FROM incidents
        ORDER BY id ASC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def get_feedback():
    connection = get_db()

    rows = connection.execute("""
        SELECT * FROM feedback
        ORDER BY id ASC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def get_latest_feedback():
    connection = get_db()

    rows = connection.execute("""
        SELECT f.*
        FROM feedback f
        INNER JOIN (
            SELECT incident_id, MAX(id) AS latest_id
            FROM feedback
            GROUP BY incident_id
        ) latest
        ON f.id = latest.latest_id
        ORDER BY f.id ASC
    """).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip().lower()
    )


def unique_incidents(incidents):
    unique = []
    seen = set()

    for incident in incidents:

        key = (
            normalize(incident["employee_id"]),
            normalize(incident["department"]),
            normalize(incident["problem"]),
            normalize(incident["workaround"])
        )

        if key not in seen:
            seen.add(key)
            unique.append(incident)

    return unique


# ---------------- INTELLIGENCE ENGINE ----------------

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were",
    "to", "from", "in", "on", "and", "or", "of",
    "for", "with", "i", "we", "it", "this", "that",
    "by", "my", "our", "not", "do", "did", "their",
    "has", "have", "had", "they", "them", "then",
    "when", "where", "what", "which", "while",
    "into", "also", "been", "being", "can", "could"
}


def get_keywords(text):
    words = re.findall(
        r"[a-zA-Z]{3,}",
        str(text).lower()
    )

    return {
        word for word in words
        if word not in STOP_WORDS
    }


def build_analysis():

    incidents = unique_incidents(get_incidents())
    feedback = get_latest_feedback()

    confirmed = set()
    rejected = set()

    for item in feedback:

        if item["decision"].lower() == "confirmed":
            confirmed.add(item["incident_id"])

        elif item["decision"].lower() == "rejected":
            rejected.add(item["incident_id"])

    departments = sorted({
        item["department"] for item in incidents
    })

    lines = []

    lines.append("ECHOTRACE AI - OPERATIONAL INTELLIGENCE")
    lines.append("=" * 55)

    lines.append(
        f"Total recorded experiences: {len(incidents)}"
    )

    lines.append(
        f"Departments involved: {', '.join(departments) or 'None'}"
    )

    # ---------------- INCIDENTS ----------------

    lines.append("\nRECORDED EXPERIENCES")
    lines.append("-" * 40)

    for item in incidents:

        lines.append(
            f"\nIncident #{item['id']} - {item['department']}"
        )

        lines.append(f"Employee: {item['employee_id']}")
        lines.append(f"Problem: {item['problem']}")
        lines.append(f"Workaround: {item['workaround']}")

    # ---------------- FEEDBACK ----------------

    lines.append("\nEMPLOYEE FEEDBACK AND LEARNING")
    lines.append("-" * 40)

    lines.append(f"Confirmed incidents: {len(confirmed)}")
    lines.append(f"Rejected incidents: {len(rejected)}")

    for item in incidents:

        if item["id"] in confirmed:
            lines.append(
                f"Incident #{item['id']}: Employee confirmed this experience."
            )

        elif item["id"] in rejected:
            lines.append(
                f"Incident #{item['id']}: Employee rejected this experience."
            )

    # ---------------- CROSS-DEPARTMENT PATTERNS ----------------

    lines.append("\nPOSSIBLE CROSS-DEPARTMENT PATTERNS")
    lines.append("-" * 40)

    pattern_count = 0

    for i in range(len(incidents)):

        for j in range(i + 1, len(incidents)):

            first = incidents[i]
            second = incidents[j]

            if first["department"] == second["department"]:
                continue

            first_words = get_keywords(
                first["problem"] + " " + first["workaround"]
            )

            second_words = get_keywords(
                second["problem"] + " " + second["workaround"]
            )

            shared = sorted(first_words & second_words)

            if len(shared) >= 2:

                pattern_count += 1

                lines.append(
                    f"\nRelated experiences: #{first['id']} and #{second['id']}"
                )

                lines.append(
                    f"Departments: {first['department']} and {second['department']}"
                )

                lines.append(
                    "Common terms: " + ", ".join(shared[:8])
                )

                if (
                    first["id"] in confirmed
                    or second["id"] in confirmed
                ):
                    lines.append(
                        "Employee learning signal: At least one experience was confirmed."
                    )

                lines.append(
                    "Suggested investigation: Examine the shared process, "
                    "system integration and data flow."
                )

    if pattern_count == 0:
        lines.append(
            "No possible cross-department patterns found yet."
        )

    # ---------------- HINDSIGHT RECALL ----------------

    lines.append("\nHINDSIGHT HISTORICAL MEMORY")
    lines.append("-" * 40)

    query = (
        "Recall historical employee experiences, operational problems, "
        "recurring issues, departments, workarounds, feedback, "
        "corrective actions and outcomes. "
        + " ".join(
            item["problem"] + " " + item["workaround"]
            for item in incidents
        )
    )

    memory_result = recall_memories(query)
    memories = clean_memory_result(memory_result)

    if memory_result is None:

        lines.append(
            "Hindsight memory service is currently unavailable."
        )

    elif not memories:

        lines.append(
            "No related historical memories were returned."
        )

    else:

        lines.append(
            f"Historical memories recalled: {len(memories)}"
        )

        displayed = set()
        displayed_count = 0

        for memory in memories:

            memory_text = memory.get("text", "").strip()

            if not memory_text:
                continue

            normalized_text = normalize(memory_text)

            if normalized_text in displayed:
                continue

            displayed.add(normalized_text)
            displayed_count += 1

            lines.append(
                f"\nHistorical Memory #{displayed_count}"
            )

            lines.append(
                f"Memory type: {memory.get('type', 'experience')}"
            )

            lines.append(
                f"Insight: {memory_text[:1000]}"
            )

            if displayed_count >= 10:
                break

        if displayed_count == 0:
            lines.append(
                "No readable memory information was returned."
            )

    # ---------------- HISTORICAL WORKAROUNDS ----------------

    lines.append("\nHISTORICAL WORKAROUND KNOWLEDGE")
    lines.append("-" * 40)

    workaround_count = 0
    seen_workarounds = set()

    for item in incidents:

        workaround = item["workaround"].strip()

        if not workaround:
            continue

        key = normalize(workaround)

        if key in seen_workarounds:
            continue

        seen_workarounds.add(key)
        workaround_count += 1

        lines.append(
            f"\n{item['department']}: {workaround}"
        )

    if workaround_count == 0:
        lines.append("No historical workarounds recorded.")

    # ---------------- RECOMMENDATIONS ----------------

    lines.append("\nRECOMMENDED ACTIONS")
    lines.append("-" * 40)

    lines.append("1. Investigate recurring issues across departments.")
    lines.append("2. Prioritize experiences confirmed by employees.")
    lines.append("3. Review rejected experiences before drawing conclusions.")
    lines.append("4. Record outcomes after corrective actions.")
    lines.append("5. Compare new incidents with Hindsight historical memories.")
    lines.append("6. Investigate repeated manual workarounds for possible process improvements.")

    lines.append(
        "\nIMPORTANT: AI-generated patterns and historical memories "
        "are investigation signals, not independently verified root causes."
    )

    return "\n".join(lines), memory_result, memories


# ---------------- MAIN DASHBOARD ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- FEEDBACK PAGE ----------------

@app.route("/feedback")
def feedback_page():
    return render_template("feedback.html")


# ---------------- INCIDENT API ----------------

@app.route("/api/incidents", methods=["GET", "POST"])
def incidents_api():

    if request.method == "GET":
        return jsonify(get_incidents())

    data = request.get_json(silent=True) or {}

    employee_id = str(data.get("employee_id", "")).strip()
    department = str(data.get("department", "")).strip()
    problem = str(data.get("problem", "")).strip()
    workaround = str(data.get("workaround", "")).strip()

    if not all([employee_id, department, problem, workaround]):
        return jsonify({
            "error": "Please fill in all fields."
        }), 400

    existing = get_incidents()

    for item in existing:

        if (
            normalize(item["employee_id"]) == normalize(employee_id)
            and normalize(item["department"]) == normalize(department)
            and normalize(item["problem"]) == normalize(problem)
            and normalize(item["workaround"]) == normalize(workaround)
        ):
            return jsonify({
                "message": "This experience has already been recorded.",
                "incident_id": item["id"],
                "duplicate": True
            }), 200

    connection = get_db()

    try:

        cursor = connection.execute("""
            INSERT INTO incidents
            (employee_id, department, problem, workaround)
            VALUES (?, ?, ?, ?)
        """, (
            employee_id,
            department,
            problem,
            workaround
        ))

        incident_id = cursor.lastrowid

        connection.commit()

    finally:
        connection.close()

    content = (
        f"Incident ID {incident_id} reported by employee "
        f"{employee_id} in {department}. "
        f"Problem: {problem}. Workaround: {workaround}."
    )

    retained = retain_memory(
        content=content,
        context=f"EchoTrace employee incident {incident_id}"
    )

    return jsonify({

        "message": (
            "Experience saved successfully and sent to Hindsight memory."
            if retained else
            "Experience saved in the database. Hindsight retention needs attention."
        ),

        "incident_id": incident_id,
        "memory_saved": retained

    }), 201


# ---------------- UNIQUE FEEDBACK INCIDENTS ----------------

@app.route("/api/feedback/incidents", methods=["GET"])
def feedback_incidents_api():

    return jsonify(unique_incidents(get_incidents()))


# ---------------- FEEDBACK API ----------------

@app.route("/api/feedback", methods=["GET", "POST"])
def feedback_api():

    if request.method == "GET":
        return jsonify(get_latest_feedback())

    data = request.get_json(silent=True) or {}

    try:
        incident_id = int(data.get("incident_id"))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid incident ID."
        }), 400

    decision = str(
        data.get("decision", data.get("status", ""))
    ).strip().lower()

    outcome = str(data.get("outcome", "")).strip()

    if decision not in ("confirmed", "rejected"):
        return jsonify({
            "error": "Choose confirmed or rejected."
        }), 400

    if not outcome:
        return jsonify({
            "error": "Please enter the actual outcome."
        }), 400

    incidents = get_incidents()

    if not any(item["id"] == incident_id for item in incidents):
        return jsonify({
            "error": "Incident not found."
        }), 404

    connection = get_db()

    try:

        existing = connection.execute("""
            SELECT id
            FROM feedback
            WHERE incident_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (incident_id,)).fetchone()

        if existing:

            connection.execute("""
                UPDATE feedback
                SET decision = ?,
                    outcome = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                decision,
                outcome,
                existing["id"]
            ))

            connection.commit()

            return jsonify({
                "message": "Existing feedback updated successfully.",
                "updated": True
            })

        connection.execute("""
            INSERT INTO feedback
            (incident_id, decision, outcome)
            VALUES (?, ?, ?)
        """, (
            incident_id,
            decision,
            outcome
        ))

        connection.commit()

    finally:
        connection.close()

    retained = retain_memory(
        content=(
            f"Employee feedback for incident {incident_id}: "
            f"{decision}. Outcome: {outcome}"
        ),
        context=f"EchoTrace feedback for incident {incident_id}"
    )

    return jsonify({
        "message": (
            "Feedback saved successfully and sent to Hindsight."
            if retained else
            "Feedback saved successfully. Hindsight retention needs attention."
        ),
        "updated": False,
        "memory_saved": retained
    }), 201


# ---------------- ANALYSIS API ----------------

@app.route("/api/analyze", methods=["POST"])
def analyze_api():

    try:

        analysis, memory_result, memories = build_analysis()

        return jsonify({

            "analysis": analysis,

            "memory_available": memory_result is not None,

            "memory_result": {
                "results": memories
            },

            "related_memories": len(memories),

            "related_memories_count": len(memories)

        })

    except Exception as error:

        app.logger.exception("Analysis failed")

        return jsonify({
            "error": str(error)
        }), 500


# ---------------- DASHBOARD STATS ----------------

@app.route("/api/stats", methods=["GET"])
def stats_api():

    incidents = unique_incidents(get_incidents())

    departments = {
        item["department"] for item in incidents
    }

    return jsonify({

        "total_incidents": len(incidents),

        "total_departments": len(departments)

    })


# ---------------- START APPLICATION ----------------

if __name__ == "__main__":

    initialize_memory()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
