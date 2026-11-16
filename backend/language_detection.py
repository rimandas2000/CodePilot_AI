"""Conservative language detection for the supported CodePilot editors."""

import re

LANGUAGES = ("Python", "C", "C++", "Java", "JavaScript")
EXTENSIONS = {".py": "Python", ".c": "C", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".java": "Java", ".js": "JavaScript", ".mjs": "JavaScript"}


def detect_language(code: str, filename: str = "") -> str | None:
    """Return a language when evidence is strong; otherwise leave selection alone."""
    from pathlib import Path

    suffix = Path(filename).suffix.lower()
    if suffix in EXTENSIONS:
        return EXTENSIONS[suffix]
    if not code or not code.strip():
        return None
    text = re.sub(r"```(?:python|py|c\+\+|cpp|c|java|javascript|js)?\s*\n|```", "", code, flags=re.I)
    rules = {
        "Python": [(r"(?m)^\s*(?:def |async def |from \w+ import |import \w+|class \w+.*:|if __name__\s*==)", 5), (r"(?m)^\s*(?:print\(|elif .*:|except .*:|with .*:)", 3)],
        "C": [(r"#\s*include\s*<\s*(?:stdio|stdlib|string|stdint|stdbool)\.h\s*>", 8), (r"\b(?:printf|scanf|malloc|free|puts|fgets)\s*\(", 5), (r"\b(?:int|void)\s+main\s*\([^)]*\)\s*\{", 3)],
        "C++": [(r"#\s*include\s*<\s*(?:iostream|vector|string|algorithm|map|bits/stdc\+\+\.h)\s*>", 9), (r"\b(?:std::|cout\s*<<|cin\s*>>|using\s+namespace\s+std)\b", 7), (r"\btemplate\s*<|\bclass\s+\w+\s*:\s*public\b", 5)],
        "Java": [(r"\bpublic\s+static\s+void\s+main\s*\(", 9), (r"\bSystem\.out\.print(?:ln)?\s*\(", 8), (r"\bpublic\s+class\s+\w+|\bimport\s+java\.", 6)],
        "JavaScript": [(r"\b(?:const|let)\s+\w+\s*=|\bconsole\.log\s*\(", 6), (r"\b(?:function\s+\w+\s*\(|=>|document\.|require\s*\(|module\.exports|export\s+default)\b", 5)],
    }
    scores = {language: sum(weight for pattern, weight in patterns if re.search(pattern, text)) for language, patterns in rules.items()}
    best = max(scores, key=scores.get)
    if scores[best] < 3 or list(scores.values()).count(scores[best]) > 1:
        return None
    return best
