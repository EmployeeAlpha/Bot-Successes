# stoicism_test.py

STOIC_QUESTIONS = [
    "I remain calm in the face of adversity.",
    "I focus on what I can control and let go of what I cannot.",
    "I accept misfortune without complaint.",
    "I reflect before reacting emotionally.",
    "I believe that suffering can be a path to wisdom.",
    "I do not chase after pleasure or avoid discomfort at all costs.",
    "I practice mindfulness or self-awareness daily.",
    "I value virtue over material success.",
    "I strive to live according to reason and nature.",
    "I try to maintain inner peace regardless of external events."
]

def calculate_score(answers):
    if not answers:
        return 0
    return round(sum(answers) / len(answers), 2)

def interpret_score(score):
    if score >= 4.0:
        return "High Stoicism"
    elif score >= 3.0:
        return "Moderate Stoicism"
    else:
        return "Low Stoicism"
