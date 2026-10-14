"""NIL decision rule used in our reproduction (compare with Eq. 10 of the NIL paper)."""

EPSILON = 0.5

CANDIDATE_SCORES = {
    "Jaguar (car maker)": {"Jaguar Cars": 0.81, "Jaguar (animal)": 0.47},
    "the birds": {"The Birds (film)": 0.50, "The Birds (play)": 0.31},
    "Mercury": {"Mercury (planet)": 0.49, "Freddie Mercury": 0.49},
    "Apple": {"Apple Inc.": 0.92, "Apple (fruit)": 0.88},
    "phoenix": {"Phoenix, Arizona": 0.505, "Phoenix (mythology)": 0.495},
}


def link(scores, epsilon=EPSILON):
    best, score = max(scores.items(), key=lambda item: item[1])
    if score > epsilon:
        return best
    return "NIL"


if __name__ == "__main__":
    results = {mention: link(scores) for mention, scores in CANDIDATE_SCORES.items()}
    nil_count = sum(1 for entity in results.values() if entity == "NIL")
    for mention, entity in results.items():
        print(f"{mention} -> {entity}")
    print(f"NIL: {nil_count}/{len(results)}")
