import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix, accuracy_score
from sklearn.metrics import classification_report

from app.main import bootstrap_app, create_initial_session_state, process_user_message


DATA_PATH = Path("sms_conversations.json")
FAILED_CASES_PATH = Path("failed_cases.json")

LABELS = ["continue", "schedule", "end"]


def load_data():
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_label(value):
    if not value:
        return None
    return str(value).strip().lower()


def evaluate():
    print("Starting evaluation...")

    agents = bootstrap_app()
    data = load_data()

    y_true = []
    y_pred = []
    failed_cases = []

    for conv in data:
        conversation_id = conv.get("conversation_id")

        state = create_initial_session_state()["conversation_state"]
        chat_history = []

        for turn in conv["turns"]:
            speaker = turn.get("speaker")
            text = turn.get("text", "")
            expected = normalize_label(turn.get("label"))
            turn_id = turn.get("turn_id")

            if speaker == "candidate":
                chat_history.append({
                    "role": "user",
                    "content": text,
                })
                continue

            if speaker == "recruiter" and expected:
                if not chat_history:
                    chat_history.append({
                        "role": "assistant",
                        "content": text,
                    })
                    continue
                
                result = process_user_message(
                    agents=agents,
                    applicant_info={},
                    chat_history=chat_history,
                    conversation_state=state,
                )

                state = result["conversation_state"]
                assistant_message = result.get("assistant_message", "")
                predicted = normalize_label(state.get("last_action"))

                y_true.append(expected)
                y_pred.append(predicted)

                if predicted != expected:
                    failed_cases.append({
                        "conversation_id": conversation_id,
                        "turn_id": turn_id,
                        "expected": expected,
                        "predicted": predicted,
                        "input_recruiter_text": text,
                        "assistant_message": assistant_message,
                        "chat_history_before_prediction": chat_history.copy(),
                    })

                chat_history.append({
                    "role": "assistant",
                    "content": text,
                })

    accuracy = accuracy_score(y_true, y_pred)

    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    df_cm = pd.DataFrame(cm, index=LABELS, columns=LABELS)

    print("\n=== EVALUATION RESULTS ===")
    print(f"Total evaluated turns: {len(y_true)}")
    print(f"Accuracy: {accuracy:.2%}")

    print("\n=== CONFUSION MATRIX ===")
    print(df_cm)

    with FAILED_CASES_PATH.open("w", encoding="utf-8") as f:
        json.dump(failed_cases, f, indent=2, ensure_ascii=False)

    print(f"\nFailed cases saved to: {FAILED_CASES_PATH}")
        
if __name__ == "__main__":
    evaluate()