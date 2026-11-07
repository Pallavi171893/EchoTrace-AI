
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()

API_KEY = os.getenv("HINDSIGHT_API_KEY")
BASE_URL = os.getenv(
    "HINDSIGHT_BASE_URL",
    "https://api.hindsight.vectorize.io"
)

BANK_ID = "echotrace-ai"

if not API_KEY:
    raise ValueError("HINDSIGHT_API_KEY is missing in .env")

# Connect to Hindsight
client = Hindsight(
    base_url=BASE_URL,
    api_key=API_KEY
)

def setup_memory():
    client.create_bank(
        bank_id=BANK_ID,
        name="EchoTrace AI",
        background=(
            "Remember employee workarounds, recurring "
            "operational problems, their causes and outcomes."
        )
    )
    print("EchoTrace AI memory bank created!")

def store_incident(employee, department, problem, workaround):
    content = (
        f"Employee: {employee}. "
        f"Department: {department}. "
        f"Problem: {problem}. "
        f"Workaround: {workaround}."
    )

    client.retain(
        bank_id=BANK_ID,
        content=content,
        context="Employee workaround incident"
    )

    return "Incident stored in Hindsight memory!"

def recall_incidents(question):
    result = client.recall(
        bank_id=BANK_ID,
        query=question
    )

    return [memory.text for memory in result.results]

def discover_hidden_problems(question):
    response = client.reflect(
        bank_id=BANK_ID,
        query=question
    )

    return response.text


if __name__ == "__main__":
    setup_memory()

    store_incident(
        "E01",
        "Sales",
        "Orders are not synchronized",
        "Manually entering orders into another system"
    )

    print("\nRelated memories:")
    print(recall_incidents(
        "What problems occur during order synchronization?"
    ))

    print("\nAI analysis:")
    print(discover_hidden_problems(
        "Analyze the remembered employee incidents. "
        "Identify recurring problems and possible root causes. "
        "Cite the supporting incidents and do not invent facts."
    ))

    client.close()
