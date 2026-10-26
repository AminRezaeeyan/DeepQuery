"""Recall@k for a retriever, from the rank of the gold entity per query."""

# 0-based rank of the gold entity in each query's candidate list; None = not retrieved.
GOLD_RANKS = [0, 3, None, 9, 10, 1, 63, 64, None, 0, 2, 15, 9, 31, 7, 100, 0, 5, 49, 12]


def recall_at_k(ranks, k):
    hits = sum(1 for r in ranks if r is not None and r <= k)
    return hits / len(ranks)


if __name__ == "__main__":
    for k in (1, 10, 64):
        print(f"R@{k} = {recall_at_k(GOLD_RANKS, k):.2f}")
